# TRADERAGENT — Архитектура Live Trading Bot

> Версия: v3.0 | Дата: 2026-02-28

---

## 1. Точки входа и инициализация

```
bot/main.py → BotApplication
│
├── __init__()
│   ├─ ConfigManager          — загрузка YAML-конфига
│   ├─ DatabaseManager        — PostgreSQL (credentials, state, history)
│   ├─ BotOrchestrator[]      — один экземпляр на каждый бот в конфиге
│   ├─ TelegramBot            — уведомления и команды
│   ├─ MetricsCollector       — сбор метрик для Prometheus
│   ├─ AlertHandler           — вебхуки алертов (port 8080)
│   ├─ _portfolio_risk_manager — PortfolioRiskManager (общий капитал N ботов)
│   ├─ _pair_template_manager  — PairTemplateManager (ATR-конфиги для новых пар)
│   ├─ _scanner               — MarketScanner (авто-выбор пар)
│   └─ _scanner_task          — asyncio.Task (_scanner_loop)
│
├── initialize()
│   ├─ Загрузить конфиг из CONFIG_PATH (default: configs/production.yaml)
│   ├─ Инициализировать PostgreSQL
│   ├─ Инициализировать PortfolioRiskManager (total_capital из суммы ботов)
│   ├─ Для каждого bot_config:
│   │   ├─ Загрузить API-ключи из БД (зашифрованы Fernet)
│   │   ├─ Выбрать клиент биржи:
│   │   │   ├─ Bybit + sandbox=true → ByBitDirectClient (demo: api-demo.bybit.com)
│   │   │   └─ иначе → ExchangeAPIClient (CCXT wrapper)
│   │   ├─ Создать BotOrchestrator
│   │   └─ auto_start=true → запустить немедленно
│   └─ Если auto_trade.enabled:
│       ├─ Создать MarketScanner (pair list, min_volume_usdt)
│       ├─ Создать PairTemplateManager
│       └─ Запустить _scanner_loop как asyncio.Task
│
├── add_bot(bot_config) → BotOrchestrator | None
│   ├─ Создать exchange client
│   ├─ Создать и запустить BotOrchestrator
│   ├─ Зарегистрировать в _orchestrators dict
│   └─ Уведомить Telegram
│
├── remove_bot(bot_name) → None
│   ├─ Graceful stop BotOrchestrator
│   ├─ Удалить из _orchestrators
│   └─ Уведомить Telegram
│
├── _scanner_loop() → None   [фоновая задача, interval_minutes из ScannerConfig]
│   ├─ scanner.scan() → top-N пар
│   ├─ Новые пары → add_bot() с конфигом от PairTemplateManager
│   └─ Устаревшие пары → remove_bot()
│
└── start()
    ├─ MetricsExporter (HTTP :9100, Prometheus)
    ├─ MetricsCollector (background loop)
    ├─ AlertHandler (HTTP :8080)
    └─ TelegramBot (event-driven)
```

---

## 2. Машина состояний бота

```
STOPPED
  ↓ start()
STARTING
  ├─ Получить текущую цену
  ├─ Загрузить сохранённое состояние из PostgreSQL
  ├─ Инициализировать grid-ордера (если стратегия grid/hybrid)
  ├─ Запустить торговые движки
  └─ Запустить async-задачи
  ↓
RUNNING ←──────────────────────────────────┐
  ├─ pause()  → PAUSED ─────────────────→ resume()
  ├─ emergency_stop() → EMERGENCY
  └─ stop()   → STOPPED
```

---

## 3. Параллельные async-задачи

```
BotOrchestrator.start()
├── Task 1: _main_loop()             [цикл 1 сек]   — торговая логика
├── Task 2: _price_monitor()         [цикл 5 сек]   — получение цены, публикация PRICE_UPDATED
├── Task 3: _regime_monitor_loop()   [цикл 60 сек]  — детекция рыночного режима
└── Task 4: health_monitor.start()   [цикл 30 сек]  — мониторинг здоровья стратегий
```

---

## 4. Главный торговый цикл (_main_loop, каждые 1 сек)

```
while _running:

  1. ПАУЗА?
     └─ if paused: sleep(1), continue

  2. СБРОС ДНЕВНОГО СЧЁТЧИКА
     └─ if UTC day changed: risk_manager.reset_daily_loss()

  3. КЭШИРОВАНИЕ БАЛАНСА
     └─ balance = await exchange.fetch_balance()

  4. ОБНОВЛЕНИЕ АКТИВНЫХ СТРАТЕГИЙ (рыночный режим)
     └─ _update_active_strategies()
         ├─ Получить текущий режим рынка
         ├─ Сопоставить режим → рекомендуемые стратегии
         ├─ Проверить cooldown переключения (600 сек)
         └─ graceful_transition(деактивируемые, новые)

  5. ОБРАБОТКА СТРАТЕГИЙ

     A. GRID (_process_grid_orders):
        ├─ Получить открытые ордера с биржи
        ├─ Найти исполненные ордера (сравнить ID)
        ├─ handle_order_filled() → сформировать ребалансировочный ордер
        └─ Разместить новые ордера на бирже

     B. DCA (_process_dca_logic):
        ├─ dca_engine.update_price(current_price)
        ├─ if dca_triggered:
        │   ├─ risk_manager.check_trade()
        │   ├─ exchange.create_order(buy)
        │   └─ publish DCA_TRIGGERED
        └─ if tp_triggered:
            ├─ exchange.create_order(sell all)
            ├─ dca_engine.close_position()
            └─ publish TAKE_PROFIT_HIT

     C. TREND FOLLOWER (_process_trend_follower_logic):
        ├─ exchange.fetch_ohlcv(1h, limit=100) → DataFrame
        ├─ strategy.analyze_market(df)
        ├─ strategy.generate_signal(df, balance) → signal | None
        ├─ if signal:
        │   ├─ risk_manager.check_trade()
        │   ├─ exchange.create_order()
        │   └─ publish ORDER_PLACED
        └─ strategy.update_positions(price, df)
            └─ if exit: exchange.close_order() + publish ORDER_FILLED

     D. SMC (_process_smc_logic):
        ├─ БЫСТРЫЙ ПУТЬ (каждую итерацию): check TP/SL активных позиций
        └─ ПОЛНЫЙ АНАЛИЗ (каждые 300 сек):
            ├─ fetch_ohlcv x4 таймфрейма (1d, 4h, 1h, 15m)
            ├─ strategy.analyze_market(df_d1, df_4h, df_1h, df_15m)
            ├─ strategy.generate_signal(df_15m, balance) → signal | None
            └─ if signal: risk_check → create_order → publish

  6. ОБНОВЛЕНИЕ РИСК-МЕНЕДЖЕРА
     ├─ risk_manager.update_balance(balance)
     ├─ Проверить portfolio stop-loss (drawdown > limit)
     └─ if limit hit: emergency_stop()

  7. СОХРАНЕНИЕ СОСТОЯНИЯ (каждые 30 сек)
     └─ save_state() → PostgreSQL (BotStateSnapshot)

  8. sleep(1)
```

---

## 5. Слой бирж

```
BotOrchestrator.exchange
    │
    ├── ByBitDirectClient (Bybit + sandbox=true)
    │   ├─ BASE URL: api-demo.bybit.com
    │   ├─ AUTH: HMAC-SHA256 (X-BAPI-SIGN)
    │   ├─ Методы: fetch_balance, fetch_ticker, fetch_ohlcv,
    │   │          create_order, fetch_open_orders, cancel_order
    │   └─ aiohttp.ClientSession (async HTTP)
    │
    └── ExchangeAPIClient (CCXT wrapper, остальные биржи)
        ├─ LIBRARY: ccxt.pro (async)
        ├─ RATE LIMIT: async lock + adaptive interval (min 100ms)
        ├─ RETRY: tenacity (3 попытки, exponential backoff)
        └─ STATS: _request_count, _error_count, _latencies[]
```

---

## 6. Стратегии

### 6.1 Grid (bot/core/grid_engine.py)

```
GridEngine
├─ ИНИТ: symbol, upper_price, lower_price, grid_levels, amount_per_grid, profit_per_grid
├─ calculate_grid_levels() → [Decimal]  — арифметическое/геометрическое деление
├─ initialize_grid(price)               — BUY ниже цены, SELL выше
├─ handle_order_filled(id, price, amt)  — создать ребалансировочный ордер
└─ STATE: grid_orders[], active_orders{}, total_profit, buy_count, sell_count
```

### 6.2 DCA (bot/core/dca_engine.py)

```
DCAEngine
├─ ИНИТ: trigger_percentage, amount_per_step, max_steps, take_profit_percentage
├─ check_dca_trigger(price) → bool      — цена упала на trigger%?
├─ execute_dca_step(price)              — усредниться, обновить avg_entry_price
├─ update_price(price) → dict           — {dca_triggered, tp_triggered, sl_triggered}
├─ close_position(price) → Decimal      — PnL, сброс состояния
└─ STATE: position, last_buy_price, highest_price, total_dca_steps, realized_profit
```

### 6.3 Trend Follower (bot/strategies/trend_follower/)

```
TrendFollowerStrategy
├─ ИНДИКАТОРЫ: EMA(20/50), ATR(14), RSI(14), BB(20,2.0), Volume
├─ УСЛОВИЯ ВХОДА:
│   ├─ EMA crossover (fast > slow для LONG)
│   ├─ Цена закрытия выше верхней BB
│   ├─ RSI в зоне 30-70
│   ├─ Volume > 1.5x средний
│   └─ ATR > 5% от цены
├─ open_position(signal, size) → position_id
├─ update_position(id, price, df) → exit_reason | None
│   ├─ TP: entry + ATR * tp_multiplier
│   ├─ SL: entry - ATR * sl_multiplier
│   └─ Trailing stop: сдвиг SL вслед за ценой
└─ close_position(id, reason, price)
```

### 6.4 SMC (bot/strategies/smc/)

```
SMCStrategyAdapter → SMCStrategy
├─ ТАЙМФРЕЙМЫ: 1D (макро), 4H (структура), 1H (рабочий), 15M (вход)
├─ СИГНАЛЫ: FVG, Liquidity Sweep, Break of Structure
├─ ФИЛЬТРЫ: Volume, Risk/Reward ≥ 1:2, цена не старше 2%
├─ ДРОССЕЛИРОВАНИЕ: полный анализ каждые 300 сек
└─ STATE: active_positions[], closed_trades[], _cached_dfs{}
```

### 6.5 Паттерн адаптеров

```
BaseStrategy (abstract)
    ├─ analyze_market(*dfs) → BaseMarketAnalysis
    ├─ generate_signal(df, balance) → BaseSignal | None
    ├─ open_position(signal, size) → position_id
    ├─ update_positions(price, df) → [(id, exit_reason)]
    └─ close_position(id, reason, price)

Адаптеры:
    GridAdapter → GridEngine
    DCAAdapter → DCAEngine
    TrendFollowerAdapter → TrendFollowerStrategy
    SMCStrategyAdapter → SMCStrategy
```

---

## 7. Риск-менеджмент

### 7.1 Per-Bot RiskManager (bot/core/risk_manager.py)

```
RiskManager
├─ check_order_size(value) → RiskCheckResult
│   └─ value >= min_order_size
├─ check_trade(value, position_value, balance) → RiskCheckResult
│   ├─ position + value <= max_position_size
│   ├─ balance >= value
│   └─ daily_loss <= max_daily_loss
├─ update_balance(balance)
│   ├─ Обновить peak_balance (для drawdown)
│   └─ Проверить portfolio stop-loss: balance < initial * (1 - stop_loss_pct)
└─ STATE: current_balance, peak_balance, daily_loss, is_halted, halt_reason
```

### 7.2 PortfolioRiskManager (bot/core/portfolio_risk_manager.py)

Управляет общим капиталом, распределённым между N ботами:

```
SharedCapitalPool
├─ allocate(bot_name, amount) → bool
│   ├─ Проверить глобальный лимит: total_allocated + amount <= total * max_utilization_pct
│   ├─ Проверить per-bot лимит: allocated[bot] + amount <= bot_max_limit
│   └─ Зарезервировать: allocated[bot] += amount
├─ release(bot_name, amount)  — вернуть капитал, не уходить ниже 0
├─ get_utilization() → float  — total_allocated / total_capital
├─ get_available() → Decimal  — max_allowed - total_allocated
└─ update_deployed(bot_name, deployed_amount)  — фактически использованный капитал

PortfolioRiskManager
├─ check_allocation(bot_name, amount, balance?, symbol?) → RiskCheckResult
│   ├─ if is_portfolio_halted(): REJECTED_PORTFOLIO_HALTED
│   ├─ if amount > balance * max_single_pair_pct: REJECTED_PAIR_LIMIT
│   ├─ if pool.allocate() failed: REJECTED_EXPOSURE
│   ├─ if symbol correlated with active: REJECTED_CORRELATION
│   └─ else: APPROVED (но НЕ подтверждает аллокацию)
├─ confirm_allocation(bot_name, amount, symbol?) — зафиксировать, добавить в _active_symbols
├─ release_allocation(bot_name, amount, symbol?) — освободить, убрать из _active_symbols
├─ update_all_balances(balances: dict[str, Decimal])
│   ├─ Обновить _peak_value = max(_peak_value, sum(balances))
│   └─ if (peak - current) / peak >= stop_loss_pct: halt()
├─ is_portfolio_halted() → bool
├─ resume()  — сбросить halt (ручное вмешательство)
├─ set_correlation(sym_a, sym_b, corr)  — переопределить дефолт
└─ ВСТРОЕННЫЕ КОРРЕЛЯЦИИ: BTC↔ETH=0.85, BTC↔SOL=0.75, ETH↔SOL=0.70, ...
```

**RiskCheckStatus:** `APPROVED | REJECTED_EXPOSURE | REJECTED_PAIR_LIMIT | REJECTED_PORTFOLIO_HALTED | REJECTED_CORRELATION`

**Интеграция:** `BotApplication.initialize()` создаёт один `PortfolioRiskManager` и передаёт его в каждый `BotOrchestrator`. Перед каждым ордером оркестратор вызывает `portfolio_rm.check_allocation()`.

---

## 7.3 PairTemplateManager (bot/config/pair_template.py)

ATR-based автогенерация `BotConfig` для новых торговых пар:

```
PairTemplateManager.create_config(symbol, strategy, exchange_client, base_config)
├─ fetch_ohlcv(symbol, "1h", limit=100) → DataFrame
├─ Рассчитать ATR(14) = avg(True Range)
├─ GridConfig:
│   ├─ upper_price = current_price + 2 * ATR
│   ├─ lower_price = current_price - 2 * ATR
│   ├─ grid_levels = clamp(span / ATR, 5, 50)
│   └─ amount_per_grid = из base_config
└─ DCAConfig:
    ├─ trigger_pct = 1.5 * ATR / current_price
    └─ take_profit_pct = 3.0 * ATR / current_price
```

Используется в `_scanner_loop()` и Telegram-команде `/create_bot`.

---

## 8. Детектор рыночного режима (bot/orchestrator/market_regime.py)

```
MarketRegimeDetector
├─ ИНДИКАТОРЫ: EMA(20,50), ADX, ATR%, BB, RSI, Volume Ratio
├─ РЕЖИМЫ (6 типов):
│   ├─ TIGHT_RANGE:        ADX<18, ATR<1%    → GRID
│   ├─ WIDE_RANGE:         ADX<18, ATR≥1%    → GRID
│   ├─ QUIET_TRANSITION:   ADX 22-32, ATR<2%  → HOLD
│   ├─ VOLATILE_TRANSITION: ADX 22-32, ATR≥2% → REDUCE_EXPOSURE
│   ├─ BULL_TREND:         ADX>32, EMA20>EMA50 → HYBRID (Grid+DCA+TrendFollower)
│   └─ BEAR_TREND:         ADX>32, EMA20<EMA50 → DCA
└─ ГИСТЕРЕЗИС: ADX>32 → тренд, ADX<25 → выход из тренда, ADX<18 → флэт
```

Результат `RegimeAnalysis` используется в `_update_active_strategies()` живого бота
и в `StrategyRouter` при бэктестинге (см. `bot/tests/backtesting/strategy_router.py`).

---

## 9. Конфигурация Multi-Pair (bot/config/schemas.py)

```python
class AutoTradeConfig(BaseModel):
    enabled: bool = False                  # авто-торговля включена?
    max_bots: int = 5                      # максимум одновременных ботов
    min_confidence: float = 0.65           # минимальная уверенность режима
    strategy_template: str = "hybrid"     # шаблон стратегии для новых пар
    scanner: ScannerConfig = ...          # пары, интервал, min_volume_usdt

class AppConfig(BaseModel):
    ...
    auto_trade: AutoTradeConfig = AutoTradeConfig()
```

**YAML-фрагмент:**
```yaml
auto_trade:
  enabled: false
  max_bots: 5
  min_confidence: 0.65
  strategy_template: hybrid
  scanner:
    pairs: ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    interval_minutes: 15
    min_volume_usdt: 5000000
```

---

## 10. Telegram-команды (bot/telegram/bot.py)

### Существующие команды

| Команда | Описание |
|---------|----------|
| `/status` | Статус всех ботов (режим, баланс, P&L) |
| `/pause <name>` | Приостановить бота |
| `/resume <name>` | Возобновить бота |
| `/stop <name>` | Остановить бота |
| `/emergency` | Экстренная остановка всех ботов |
| `/balance` | Текущий баланс на бирже |
| `/positions` | Открытые позиции |

### Новые Multi-Pair команды (v3.0)

| Команда | Описание |
|---------|----------|
| `/scan` | Запустить ручное сканирование, показать top-5 с режимом и рекомендацией |
| `/create_bot <symbol> <strategy>` | Создать бота по ATR-шаблону (`strategy` = grid/dca/hybrid) |
| `/delete_bot <name>` | Удалить бота (graceful stop) |
| `/portfolio` | Суммарный P&L, экспозиция, распределение капитала, статус halt |

---

## 11. Event System (bot/orchestrator/events.py)

```
Redis Pub/Sub: channel = "{bot_name}:events"

EventType:
├─ Lifecycle:   BOT_STARTED, BOT_STOPPED, BOT_PAUSED, BOT_EMERGENCY_STOP
├─ Trading:     ORDER_PLACED, ORDER_FILLED, ORDER_CANCELLED, ORDER_FAILED
├─ Strategy:    GRID_INITIALIZED, DCA_TRIGGERED, TAKE_PROFIT_HIT
├─ Market:      REGIME_DETECTED, REGIME_CHANGED, STRATEGY_SWITCH_RECOMMENDED
├─ Health:      HEALTH_CHECK_COMPLETED, HEALTH_DEGRADED, HEALTH_CRITICAL
├─ Transitions: STRATEGY_TRANSITION_STARTED, STRATEGY_TRANSITION_COMPLETED
└─ Risk:        RISK_LIMIT_HIT, STOP_LOSS_TRIGGERED, POSITION_LIMIT_REACHED

Подписчики:
    ├─ TelegramBot    — уведомления в чат
    ├─ MetricsCollector — инкремент счётчиков Prometheus
    └─ AlertHandler   — запись в БД, вебхуки
```

---

## 12. Полный поток данных: Рынок → Ордер

```
[каждые 5 сек] exchange.fetch_ticker(symbol)
    └─ current_price: Decimal

[каждую 1 сек] Для активных стратегий:
    Grid/DCA  → только цена
    TF        → fetch_ohlcv(1h, 100 свечей) → DataFrame
    SMC       → fetch_ohlcv(1d, 4h, 1h, 15m) → 4x DataFrame
    Режим     → fetch_ohlcv(1h, 200 свечей)

    ↓ АНАЛИЗ
    strategy.analyze_market(*dfs) → BaseMarketAnalysis
    strategy.generate_signal(df, balance) → BaseSignal | None

    ↓ РИСК (если сигнал есть)
    risk_manager.check_trade(order_value, position_value, balance)
    └─ REJECT если любое ограничение нарушено

    ↓ РАЗМЕР ПОЗИЦИИ
    TF/SMC: min(signal.entry * 0.1, max_position_size_usd)
    Grid/DCA: amount_per_grid | amount_per_step (из конфига)

    ↓ ОРДЕР НА БИРЖУ (если not dry_run)
    exchange.create_order(symbol, type, side, amount, price)
    └─ {'id': 'order_123', 'status': 'new'}

    ↓ ЛОКАЛЬНОЕ СОСТОЯНИЕ
    Grid → register_order(grid_order, order_id)
    DCA  → execute_dca_step(price)
    TF   → position_manager.add_position(signal, size)
    SMC  → open_position(signal, size)

    ↓ СОБЫТИЕ (Redis Pub/Sub)
    publish(ORDER_PLACED, {order_id, side, price, amount, strategy})

    ↓ МОНИТОРИНГ (каждые 1 сек)
    update_positions(current_price, df)
    └─ TP/SL hit? → close_position() → market exit → ORDER_FILLED event
```

---

## 13. Персистентность состояния

```
save_state() / load_state()  [каждые 30 сек + при остановке]
    → PostgreSQL: BotStateSnapshot

Сохраняется:
├─ Grid: grid_orders[], active_orders{}, total_profit
├─ DCA: position, step_count, avg_entry_price, realized_profit
├─ TF/SMC: active_positions[]
└─ Risk: current_balance, peak_balance, daily_loss, is_halted

При перезапуске:
└─ Сверить состояние с биржей (reconcile), восстановить открытые позиции
```

---

## 14. Стек технологий

| Компонент        | Технология                              |
|------------------|-----------------------------------------|
| Язык             | Python 3.12, asyncio                    |
| Биржа (demo)     | ByBit V5 API (aiohttp, HMAC-SHA256)     |
| Биржа (live)     | CCXT Pro (async, rate limiting, retry)  |
| БД               | PostgreSQL (asyncpg)                    |
| Кэш/события      | Redis Pub/Sub                           |
| Уведомления      | Telegram Bot API                        |
| Мониторинг       | Prometheus + structlog                  |
| Конфиг           | YAML (Pydantic validation)              |
| Шифрование       | Fernet (API credentials)                |
| Тесты            | Pytest + pytest-asyncio (1582+ тестов)  |
| Деплой           | Docker Compose (volume mount bot/)      |
