# TRADERAGENT — Архитектура Live Trading Bot

> Версия: v2.0 | Дата: 2026-02-28

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
│   └─ AlertHandler           — вебхуки алертов (port 8080)
│
├── initialize()
│   ├─ Загрузить конфиг из CONFIG_PATH (default: configs/production.yaml)
│   ├─ Инициализировать PostgreSQL
│   └─ Для каждого bot_config:
│       ├─ Загрузить API-ключи из БД (зашифрованы Fernet)
│       ├─ Выбрать клиент биржи:
│       │   ├─ Bybit + sandbox=true → ByBitDirectClient (demo: api-demo.bybit.com)
│       │   └─ иначе → ExchangeAPIClient (CCXT wrapper)
│       ├─ Создать BotOrchestrator
│       └─ auto_start=true → запустить немедленно
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

## 7. Риск-менеджмент (bot/core/risk_manager.py)

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

---

## 8. Детектор рыночного режима (bot/orchestrator/market_regime.py)

```
MarketRegimeDetector
├─ ИНДИКАТОРЫ: EMA(20,50), ADX, ATR%, BB, RSI, Volume Ratio
├─ РЕЖИМЫ (6 типов):
│   ├─ TIGHT_RANGE:        ADX<18, ATR<1%   → Grid
│   ├─ WIDE_RANGE:         ADX<18, ATR≥1%   → Grid
│   ├─ QUIET_TRANSITION:   ADX 22-32, ATR<2% → Hold
│   ├─ VOLATILE_TRANSITION: ADX 22-32, ATR≥2% → Reduce exposure
│   ├─ BULL_TREND:         ADX>32, EMA20>EMA50 → TrendFollower/Hybrid
│   └─ BEAR_TREND:         ADX>32, EMA20<EMA50 → DCA
├─ ГИСТЕРЕЗИС: ADX>32 → тренд, ADX<25 → выход из тренда, ADX<18 → флэт
└─ ⚠️ АРХИТЕКТУРНЫЙ ДОЛГ: результат detect_market_regime() не читается в _main_loop
```

---

## 9. Event System (bot/orchestrator/events.py)

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

## 10. Полный поток данных: Рынок → Ордер

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

## 11. Персистентность состояния

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

## 12. Стек технологий

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
| Тесты            | Pytest + pytest-asyncio (1587 тестов)   |
| Деплой           | Docker Compose (volume mount bot/)      |
