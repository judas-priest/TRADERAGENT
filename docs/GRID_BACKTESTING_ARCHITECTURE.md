# Grid Backtesting System — Architecture & Comparison with Live Bot

## 1. Ответ на главный вопрос

**Должна ли Grid Backtesting System имитировать работу основного бота, но использовать исторические данные вместо real-time данных биржи?**

**Да, концептуально — должна. Практически — текущая реализация делает это ЧАСТИЧНО.**

Backtesting System воспроизводит **логику grid-трейдинга** (уровни, ордера, counter-orders, циклы buy→sell), но **не является прямой симуляцией бота**. Это **независимая реализация** той же стратегии с собственными компонентами, что создаёт архитектурный разрыв (divergence risk).

---

## 2. Архитектура Live Bot (Grid Strategy)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LIVE BOT ARCHITECTURE                        │
│                    (bot/ — production runtime)                       │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────┐
                    │    bot/main.py        │
                    │   BotApplication     │
                    │  (multi-bot setup)   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   BotOrchestrator    │
                    │ bot/orchestrator/    │
                    │ bot_orchestrator.py  │
                    │                     │
                    │ • _main_loop() 1s   │
                    │ • _price_monitor()  │
                    │ • _regime_monitor() │
                    └──┬───┬───┬───┬──────┘
                       │   │   │   │
          ┌────────────┘   │   │   └────────────┐
          │                │   │                 │
┌─────────▼────────┐ ┌────▼───▼────┐  ┌────────▼─────────┐
│   Grid Engine    │ │  Exchange   │  │  Risk Manager    │
│ bot/core/        │ │  API Client │  │ bot/core/        │
│ grid_engine.py   │ │ bot/api/    │  │ risk_manager.py  │
│                  │ │             │  │                  │
│ • initialize_    │ │ • fetch_    │  │ • check_trade()  │
│   grid()        │ │   ticker()  │  │ • daily_loss     │
│ • handle_order_ │ │ • fetch_    │  │ • position_limit │
│   filled()      │ │   open_     │  │ • portfolio_stop │
│ • register_     │ │   orders()  │  └──────────────────┘
│   order()       │ │ • create_   │
│ • _create_      │ │   order()   │  ┌──────────────────┐
│   rebalance_    │ │ • cancel_   │  │ State Persistence│
│   order()       │ │   order()   │  │ bot/orchestrator/│
│                  │ │             │  │ state_           │
└────────┬─────────┘ │  REAL       │  │ persistence.py   │
         │           │  EXCHANGE   │  │                  │
┌────────▼─────────┐ │  (Bybit)   │  │ • PostgreSQL     │
│ Grid Calculator  │ └─────────────┘  │ • BotState-      │
│ bot/strategies/  │                  │   Snapshot       │
│ grid/grid_       │                  │ • reconcile_     │
│ calculator.py    │                  │   with_exchange()│
│                  │                  └──────────────────┘
│ • calculate_     │
│   levels()       │  ┌──────────────────┐
│ • calculate_atr()│  │ Grid Order Mgr   │
│ • adjust_bounds_ │  │ bot/strategies/  │
│   by_atr()       │  │ grid/grid_order_ │
│ • optimal_grid_  │  │ manager.py       │
│   count()        │  │                  │
│ • calculate_     │  │ • on_order_      │
│   grid_orders()  │  │   filled()       │
└──────────────────┘  │ • rebalance()    │
                      │ • GridCycle      │
                      │   (profit track) │
                      └──────────────────┘
```

### Ключевые характеристики Live Bot:

| Аспект | Реализация |
|--------|------------|
| **Источник данных** | Bybit API real-time (fetch_ticker каждые 5 сек) |
| **Исполнение ордеров** | Реальная биржа (create_order → exchange order_id) |
| **Обнаружение fill** | Polling: fetch_open_orders → если ордер исчез → fetch_order → status=="closed" |
| **Counter-order** | grid_engine.handle_order_filled() → _place_single_order() |
| **Риск-менеджмент** | RiskManager: daily loss, position size, portfolio stop-loss |
| **Состояние** | PostgreSQL (BotStateSnapshot), reconcile с биржей при рестарте |
| **Цикл** | Бесконечный asyncio loop, 1 сек интервал |
| **Комиссии** | Реальные (биржа удерживает) |
| **Баланс** | Реальный счёт (fetch_balance) |

---

## 3. Архитектура Grid Backtesting System

```
┌─────────────────────────────────────────────────────────────────────┐
│                   BACKTESTING SYSTEM ARCHITECTURE                    │
│              (services/backtesting/ — standalone service)            │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────┐
                    │  FastAPI Service     │
                    │  api/routes.py       │
                    │                     │
                    │ POST /backtest/run  │
                    │ POST /optimize/run  │
                    │ GET  /presets       │
                    │ GET  /chart/{id}    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │ GridBacktestSystem   │
                    │ engine/system.py    │
                    │                     │
                    │ run_full_pipeline():│
                    │ 1. Classify         │
                    │ 2. Optimize         │
                    │ 3. Stress test      │
                    │ 4. Report           │
                    └──┬───┬───┬───┬──────┘
                       │   │   │   │
          ┌────────────┘   │   │   └────────────┐
          │                │   │                 │
┌─────────▼────────┐ ┌────▼───▼────┐  ┌────────▼─────────┐
│ CoinClusterizer  │ │GridOptimizer│  │ GridBacktest-    │
│ engine/          │ │ engine/     │  │ Reporter         │
│ clusterizer.py   │ │optimizer.py │  │ engine/          │
│                  │ │             │  │ reporter.py      │
│ • classify()     │ │ • optimize()│  │                  │
│   → CoinProfile  │ │ • coarse_  │  │ • generate_      │
│   → CoinCluster  │ │   search() │  │   report()       │
│ (blue_chips,     │ │ • fine_    │  │ • export_        │
│  mid_caps,       │ │   search() │  │   preset_yaml()  │
│  memes, stable)  │ │ • parallel │  └──────────────────┘
└──────────────────┘ │   via Pool │
                     └──────┬─────┘
                            │
                 ┌──────────▼───────────┐
                 │ GridBacktestSimulator│
                 │ engine/simulator.py  │
                 │                     │
                 │ run_async(candles): │
                 │  for each candle:   │
                 │   • sweep OHLC      │
                 │   • detect fills    │
                 │   • counter-orders  │
                 │   • risk check      │
                 │   • equity tracking │
                 └──┬───┬───┬──────────┘
                    │   │   │
       ┌────────────┘   │   └────────────┐
       │                │                 │
┌──────▼───────┐ ┌──────▼──────┐ ┌───────▼───────┐
│ Grid         │ │  Market     │ │ Grid Risk     │
│ Calculator   │ │  Simulator  │ │ Manager       │
│ core/        │ │ core/       │ │ core/         │
│calculator.py │ │market_      │ │risk_manager.py│
│              │ │simulator.py │ │               │
│ (COPY of     │ │             │ │ • stop_loss   │
│  bot/strat./ │ │ • REPLACES  │ │ • drawdown    │
│  grid/grid_  │ │   Bybit API │ │               │
│  calculator) │ │ • Simulated │ └───────────────┘
│              │ │   Balance   │
│ • calculate_ │ │ • Simulated │ ┌───────────────┐
│   levels()   │ │   Orders    │ │ Grid Order    │
│ • calculate_ │ │ • Limit     │ │ Manager       │
│   atr()      │ │   order     │ │ core/         │
│ • adjust_    │ │   matching  │ │order_manager  │
│   bounds()   │ │ • Fee       │ │.py            │
└──────────────┘ │   deduction │ │               │
                 │ • Portfolio │ │ (COPY of      │
                 │   value     │ │  bot/strat./  │
                 └─────────────┘ │  grid/grid_   │
                                 │  order_mgr)   │
                 ┌───────────────┤               │
                 │ Trailing Grid │ │ • on_order_  │
                 │ Manager       │ │   filled()   │
                 │ trailing/     │ │ • rebalance()│
                 │ manager.py    │ │ • GridCycle   │
                 │               │ └───────────────┘
                 │ • check_and_ │
                 │   shift()    │ ┌───────────────┐
                 │ • cooldown   │ │ Persistence   │
                 └───────────────┘ │               │
                                 │ • JobStore     │
                                 │   (SQLite)     │
                                 │ • PresetStore  │
                                 │   (SQLite)     │
                                 │ • Checkpoint   │
                                 └───────────────┘
```

### Ключевые характеристики Backtesting System:

| Аспект | Реализация |
|--------|------------|
| **Источник данных** | CSV файлы (OHLCV свечи), загружаются в pd.DataFrame |
| **Исполнение ордеров** | MarketSimulator (in-memory), лимитные ордера матчатся по цене |
| **Обнаружение fill** | Прямое: set_price() → _check_limit_orders() → мгновенный fill |
| **Counter-order** | order_mgr.on_order_filled() → market.create_order() |
| **Риск-менеджмент** | GridRiskManager: stop-loss, drawdown (+ take-profit) |
| **Состояние** | In-memory (результат = GridBacktestResult dataclass) |
| **Цикл** | Конечный: итерация по свечам (for idx in range(len(candles))) |
| **Комиссии** | Симулированные (maker_fee=0.1%, taker_fee=0.1%) |
| **Баланс** | SimulatedBalance (quote + base, in-memory) |

---

## 4. Детальное сравнение: что общего и что различается

### 4.1 Компоненты с ДУБЛИРОВАННЫМ кодом (копии)

Эти файлы существуют в ДВУХ местах с идентичной логикой, но разными import-путями:

| Компонент | Live Bot | Backtesting | Статус |
|-----------|----------|-------------|--------|
| **GridCalculator** | `bot/strategies/grid/grid_calculator.py` | `services/backtesting/.../core/calculator.py` | КОПИЯ (import logger отличается) |
| **GridOrderManager** | `bot/strategies/grid/grid_order_manager.py` | `services/backtesting/.../core/order_manager.py` | КОПИЯ (import logger отличается) |
| **GridLevel** | `bot/strategies/grid/grid_calculator.py` | `services/backtesting/.../core/calculator.py` | КОПИЯ |
| **GridSpacing** | `bot/strategies/grid/grid_calculator.py` | `services/backtesting/.../core/calculator.py` | КОПИЯ |

**Риск:** Если исправить баг в одном месте, в другом он останется. Логика может разойтись.

### 4.2 Компоненты ЭКВИВАЛЕНТНЫЕ по роли, но РАЗНЫЕ по реализации

| Роль | Live Bot | Backtesting | Различия |
|------|----------|-------------|----------|
| **Источник цены** | `ExchangeAPIClient.fetch_ticker()` → real Bybit API | `MarketSimulator.set_price()` → из OHLCV свечей | Принципиально разное: real-time polling vs итерация |
| **Исполнение ордеров** | `ExchangeAPIClient.create_order()` → Bybit V5 API | `MarketSimulator.create_order()` → in-memory matching | Разные модели исполнения |
| **Обнаружение fill** | Polling open_orders + fetch_order(status) | Мгновенный price crossing check | Bot не видит fill мгновенно (задержка polling) |
| **Grid State Machine** | `GridEngine` (bot/core/grid_engine.py) | `GridOrderManager` (backtesting) | Разные классы, разная логика counter-orders |
| **Оркестрация** | `BotOrchestrator._main_loop()` | `GridBacktestSimulator.run_async()` | Бот = бесконечный loop, Backtest = конечный loop по свечам |
| **Риск** | `RiskManager` (daily loss, position size, portfolio stop) | `GridRiskManager` (stop-loss, drawdown, take-profit) | Разные наборы правил |
| **Состояние** | PostgreSQL + exchange reconciliation | In-memory (нет persistence во время run) | Backtest не нужна reconciliation |

### 4.3 Компоненты, ОТСУТСТВУЮЩИЕ в одной из систем

| Компонент | Live Bot | Backtesting | Причина |
|-----------|----------|-------------|---------|
| **DCA Engine** | Есть | Нет | Backtest только для Grid |
| **Trend Follower** | Есть | Нет | Backtest только для Grid |
| **Market Regime Detector** | Есть | Нет | Не используется в backtest |
| **Telegram Notifications** | Есть | Нет | Не нужно |
| **Redis Events** | Есть | Нет | Нет real-time подписчиков |
| **CoinClusterizer** | Нет | Есть | Классификация монет для оптимизации |
| **GridOptimizer** | Нет | Есть | Перебор параметров |
| **Stress Testing** | Нет | Есть | Тест на волатильных периодах |
| **TrailingGridManager** | Нет | Есть | Динамический сдвиг сетки |
| **Chart Generation** | Нет | Есть | Визуализация результатов |
| **Preset Export** | Нет | Есть | Экспорт оптимальных параметров |

---

## 5. Data Flow Comparison (визуальное сравнение потоков)

### Live Bot Data Flow:
```
Bybit Exchange ──(HTTP/5s)──▶ fetch_ticker() ──▶ current_price (Decimal)
                                                      │
                                    ┌─────────────────▼──────────────────┐
                                    │     _process_grid_orders()          │
                                    │                                     │
                                    │  1. fetch_open_orders() ──HTTP──▶ Bybit
                                    │  2. for order in active_orders:     │
                                    │     if order NOT in open_orders:    │
                                    │       fetch_order(id) ──HTTP──▶ Bybit
                                    │       if status == "closed":        │
                                    │         handle_order_filled()       │
                                    │         → counter_order             │
                                    │         create_order() ──HTTP──▶ Bybit
                                    │  3. risk_manager.check_trade()      │
                                    │  4. save_state() → PostgreSQL       │
                                    └─────────────────────────────────────┘
```

### Backtesting Data Flow:
```
CSV File ──(pd.read_csv)──▶ DataFrame[open,high,low,close,volume,timestamp]
                                   │
                    ┌──────────────▼──────────────────────┐
                    │  for idx in range(len(candles)):     │
                    │                                      │
                    │  1. Extract OHLC from row            │
                    │  2. price_sweep = [O, L, H, C]       │
                    │  3. for price in price_sweep:         │
                    │       market.set_price(price)         │
                    │       → _check_limit_orders()         │
                    │       → instant fill if price crosses │
                    │  4. for each new_trade:               │
                    │       order_mgr.on_order_filled()     │
                    │       → counter_order                 │
                    │       market.create_order(counter)    │
                    │  5. Calculate equity, drawdown        │
                    │  6. risk_mgr.evaluate_risk()          │
                    │  7. Record EquityPoint                │
                    └──────────────────────────────────────┘
                                   │
                                   ▼
                         GridBacktestResult
                    (return_pct, sharpe, trades, ...)
```

---

## 6. Ключевые архитектурные расхождения (Divergence Risks)

### 6.1 Модель исполнения ордеров

**Live Bot:**
- Ордер размещается на бирже → получает `exchange_order_id`
- Fill обнаруживается через **polling** (ордер исчезает из open_orders)
- Есть задержка обнаружения (до 1 сек main loop + до 5 сек price monitor)
- Partial fills обрабатываются
- Slippage реальный (зависит от ликвидности order book)

**Backtesting:**
- Ордер создаётся в `MarketSimulator` → мгновенный `sim_N` id
- Fill происходит **мгновенно** при `set_price()` если `current_price <= buy_price` или `>= sell_price`
- Нет задержки обнаружения
- **Нет partial fills** (всё или ничего)
- Slippage фиксированный (0.01%)

**Влияние на точность:**
- Бэктестинг **оптимистичен** — ордера исполняются идеально
- В реальности бот может пропустить fill или получить worst-case execution
- Intra-candle sweep `[O, L, H, C]` — грубое приближение реального движения цены

### 6.2 Логика counter-orders

**Live Bot (GridEngine):**
```python
def handle_order_filled(self, order_id, filled_price, filled_amount):
    # Находит ордер по order_id
    # Если BUY → создаёт SELL на price + profit_margin
    # Если SELL → создаёт BUY на price - profit_margin
    return _create_rebalance_order(...)
```

**Backtesting (GridOrderManager):**
```python
def on_order_filled(self, exchange_order_id, filled_price, filled_amount):
    # Находит GridOrderState по exchange_order_id
    # Создаёт counter GridOrderState через _create_counter_order()
    # Отслеживает GridCycle (buy→sell profit)
    return counter_order_state
```

**Различие:** Разные классы, разная внутренняя логика, но **одинаковый результат** — counter-order на противоположной стороне с profit margin.

### 6.3 Риск-менеджмент

**Live Bot RiskManager:**
- `max_daily_loss` — сброс каждый день (UTC)
- `max_position_size` — лимит позиции
- `portfolio_stop_loss` — процент от портфеля
- Emergency stop → cancel all orders → save state

**Backtesting GridRiskManager:**
- `grid_stop_loss_pct` — стоп по цене от entry
- `max_drawdown_pct` — максимальная просадка equity
- `take_profit_pct` — выход по прибыли (нет в live bot!)
- Stop → break simulation loop

**Различие:** Разные правила. Бэктестинг не тестирует `daily_loss` и `position_size` из live бота.

---

## 7. Архитектурная оценка: текущее состояние

```
┌─────────────────────────────────────────────────────────────────────┐
│                  ТЕКУЩАЯ АРХИТЕКТУРА (AS-IS)                         │
│                                                                     │
│  ┌─────────────────────┐          ┌─────────────────────┐          │
│  │     LIVE BOT        │          │   BACKTESTING       │          │
│  │                     │          │                     │          │
│  │  GridEngine         │◄─COPY──►│  GridOrderManager   │          │
│  │  GridCalculator     │◄─COPY──►│  GridCalculator     │          │
│  │  GridOrderManager   │◄─COPY──►│  GridOrderManager   │          │
│  │  ExchangeAPIClient  │  ≠≠≠≠   │  MarketSimulator    │          │
│  │  RiskManager        │  ≠≠≠≠   │  GridRiskManager    │          │
│  │  BotOrchestrator    │  ≠≠≠≠   │  BacktestSimulator  │          │
│  │                     │          │                     │          │
│  │  DCA, Trend, Hybrid │          │  Optimizer,         │          │
│  │  Telegram, Redis    │          │  Clusterizer,       │          │
│  │  PostgreSQL         │          │  Reporter, Charts   │          │
│  └─────────────────────┘          └─────────────────────┘          │
│                                                                     │
│  Проблемы:                                                          │
│  • Дублирование кода (GridCalculator, GridOrderManager)             │
│  • Разные модели риска                                              │
│  • Нет гарантии что backtest точно имитирует бота                   │
│  • Изменения в боте не отражаются автоматически в бэктестинге       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Рекомендуемая целевая архитектура (TO-BE)

### Принцип: Shared Core + Pluggable Adapters

```
┌─────────────────────────────────────────────────────────────────────┐
│                 ЦЕЛЕВАЯ АРХИТЕКТУРА (TO-BE)                          │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │              SHARED CORE (bot/strategies/grid/)         │        │
│  │                                                         │        │
│  │  GridCalculator    — расчёт уровней, ATR, bounds        │        │
│  │  GridOrderManager  — lifecycle ордеров, counter-orders   │        │
│  │  GridRiskRules     — общие правила риска                 │        │
│  │  GridConfig        — конфигурация стратегии              │        │
│  └────────────────────┬────────────────────────────────────┘        │
│                       │                                             │
│           ┌───────────┴───────────┐                                 │
│           │                       │                                 │
│  ┌────────▼────────┐    ┌────────▼─────────┐                       │
│  │  LIVE ADAPTER   │    │ BACKTEST ADAPTER  │                       │
│  │                 │    │                   │                       │
│  │ ExchangeAPI-    │    │ MarketSimulator   │                       │
│  │ Client (Bybit)  │    │ (in-memory)       │                       │
│  │                 │    │                   │                       │
│  │ implements:     │    │ implements:       │                       │
│  │ • fetch_price() │    │ • fetch_price()   │                       │
│  │ • place_order() │    │ • place_order()   │                       │
│  │ • get_fills()   │    │ • get_fills()     │                       │
│  │ • get_balance() │    │ • get_balance()   │                       │
│  └─────────────────┘    └───────────────────┘                       │
│                                                                     │
│  ┌─────────────────┐    ┌───────────────────┐                       │
│  │ LIVE RUNNER     │    │ BACKTEST RUNNER   │                       │
│  │                 │    │                   │                       │
│  │ BotOrchestrator │    │ BacktestSimulator │                       │
│  │ (infinite loop) │    │ (candle loop)     │                       │
│  │ + DCA, Hybrid   │    │ + Optimizer       │                       │
│  │ + Telegram      │    │ + Reporter        │                       │
│  │ + PostgreSQL    │    │ + Charts          │                       │
│  └─────────────────┘    └───────────────────┘                       │
│                                                                     │
│  Преимущества:                                                      │
│  • ОДИН GridCalculator, ОДИН GridOrderManager                       │
│  • Бэктестинг гарантированно тестирует ту же логику                 │
│  • Баг-фикс в core автоматически в обоих системах                  │
│  • Adapter pattern изолирует различия (real API vs simulation)      │
└─────────────────────────────────────────────────────────────────────┘
```

### Интерфейс адаптера (Protocol):

```python
class IGridExchange(Protocol):
    """Абстракция биржи для grid-стратегии."""

    async def fetch_price(self, symbol: str) -> Decimal:
        """Получить текущую цену."""
        ...

    async def place_order(
        self, symbol: str, side: str, amount: Decimal, price: Decimal
    ) -> str:
        """Разместить лимитный ордер → вернуть order_id."""
        ...

    async def cancel_order(self, order_id: str) -> None:
        """Отменить ордер."""
        ...

    async def get_open_orders(self, symbol: str) -> list[dict]:
        """Получить открытые ордера."""
        ...

    async def get_order_status(self, order_id: str) -> dict:
        """Получить статус ордера (filled/open/cancelled)."""
        ...

    async def get_balance(self) -> dict[str, Decimal]:
        """Получить баланс {quote: ..., base: ...}."""
        ...
```

---

## 9. Сводная таблица различий

| Характеристика | Live Bot | Backtesting | Идеал (TO-BE) |
|----------------|----------|-------------|---------------|
| **GridCalculator** | `bot/strategies/grid/` | `services/.../core/` (копия) | Один в `bot/strategies/grid/` |
| **GridOrderManager** | `bot/strategies/grid/` | `services/.../core/` (копия) | Один в `bot/strategies/grid/` |
| **Exchange** | Real Bybit API | MarketSimulator | IGridExchange Protocol |
| **Fill detection** | Polling (задержка) | Instant (оптимистично) | Adapter скрывает разницу |
| **Risk rules** | daily_loss + position_size | stop_loss + drawdown + TP | Объединённый набор |
| **Price data** | Real-time ticker | OHLCV candles | Adapter: `fetch_price()` |
| **State** | PostgreSQL + reconcile | In-memory | Runner-specific |
| **Partial fills** | Да | Нет | MarketSimulator должен поддерживать |
| **Trailing grid** | Нет | Да | Shared Core |
| **Fees** | Реальные (биржа) | Симулированные (0.1%) | Adapter |

---

## 10. Выводы

1. **Бэктестинг ДОЛЖЕН имитировать бота** — это его основное назначение. Чем ближе симуляция к реальному поведению, тем достовернее результаты.

2. **Текущая реализация частично имитирует**, но с существенными расхождениями:
   - Дублированный код создаёт риск divergence
   - Разные модели исполнения (instant vs polling)
   - Разные правила риска
   - MarketSimulator не поддерживает partial fills

3. **Главная архитектурная проблема** — отсутствие общего интерфейса. Бот и бэктестинг развиваются независимо, что ведёт к расхождению логики.

4. **Рекомендация**: перейти к архитектуре Shared Core + Pluggable Adapters, где grid-логика живёт в одном месте, а различия между real-time и historical изолированы в адаптерах.
