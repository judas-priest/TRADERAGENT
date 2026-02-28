# TRADERAGENT — Архитектура Backtesting Pipeline

> Версия: v3.0 | Дата: 2026-02-28

---

## 1. Две подсистемы бэктестинга

```
┌─────────────────────────────────────────────────────────────┐
│  Подсистема 1: Grid Backtesting Service                     │
│  Путь: services/backtesting/                                │
│  Статус: PRODUCTION-READY                                   │
│  Цель: Grid-стратегия, оптимизация параметров, стресс-тест  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Подсистема 2: Multi-Strategy Backtesting Framework V2.0    │
│  Путь: bot/tests/backtesting/                               │
│  Статус: PRODUCTION-READY (V2.0)                            │
│  Цель: Grid+DCA+TF+SMC, режимный маршрутизатор,             │
│        портфельный бэктест N пар, unified оптимизация       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Точки входа

```
scripts/
├── run_grid_backtest.py              — одиночный бэктест (одна пара)
├── run_grid_backtest_all.py          — batch: 45 пар, все таймфреймы
├── run_multi_strategy_backtest.py    — Grid + другие стратегии
├── run_dca_tf_smc_pipeline.py        — Phase 1-5: полный pipeline (V1)
└── run_backtest_v2.py                — V2.0: Orchestrator + Portfolio pipeline

services/backtesting/src/grid_backtester/
├── api/routes.py                     — FastAPI endpoints
└── engine/system.py                  — GridBacktestSystem (оркестратор)
```

### Запуск

```bash
# Batch по 45 парам (14 воркеров, последние 4320 свечей ≈ 6 мес)
python scripts/run_grid_backtest_all.py --workers 14 --last-candles 4320

# Одна пара
python scripts/run_grid_backtest.py BTCUSDT

# Multi-strategy pipeline (V1)
python scripts/run_dca_tf_smc_pipeline.py --data-dir data/historical/ --workers 14

# V2.0 Pipeline — одна пара
python scripts/run_backtest_v2.py --mode single --symbol BTCUSDT --workers 8

# V2.0 Pipeline — несколько пар
python scripts/run_backtest_v2.py --mode multi --symbols BTC,ETH,SOL --workers 8

# V2.0 Pipeline — авто-выбор top-N
python scripts/run_backtest_v2.py --mode auto --top-n 10 --workers 8

# API (FastAPI)
uvicorn services/backtesting/src/grid_backtester/api/app:app --reload
```

---

## 3. Архитектура Grid Backtesting Service

### 3.1 Оркестратор (GridBacktestSystem)

```
GridBacktestSystem.run_full_pipeline(symbols, candles_map)
│
├── ШАГ 1: КЛАССИФИКАЦИЯ МОНЕТЫ
│   └─ CoinClusterizer.classify(symbol, candles)
│       ├─ Рассчитать ATR%
│       └─ Кластер: STABLE | BLUE_CHIPS | MID_CAPS | MEMES
│           └─ CoinProfile {cluster, atr_pct, volatility_score}
│
├── ШАГ 2: ПОЛУЧИТЬ ПРЕСЕТ ПАРАМЕТРОВ
│   └─ CLUSTER_PRESETS[cluster] → ClusterPreset
│       └─ {spacing_options, levels_range, profit_per_grid_range, amount_per_grid_range}
│
├── ШАГ 3: ОПТИМИЗАЦИЯ (GridOptimizer)
│   ├─ Фаза 1 (Coarse): Cartesian product из preset-диапазонов
│   │   ├─ ~27–81 комбинаций
│   │   ├─ ProcessPoolExecutor (параллельно)
│   │   └─ Выбрать лучший по objective (Sharpe/ROI/Calmar)
│   └─ Фаза 2 (Fine): Уточнение вокруг лучшего coarse
│       ├─ ~27 комбинаций (3^3)
│       ├─ ProcessPoolExecutor (параллельно)
│       └─ Финальный лучший результат
│
├── ШАГ 4: СТРЕСС-ТЕСТ
│   ├─ Найти 3 самых волатильных подпериода (20–40 свечей)
│   └─ GridBacktestSimulator.run() для каждого периода
│
├── ШАГ 5: ОТЧЁТ
│   ├─ GridBacktestReporter.generate_optimization_report()
│   │   └─ best_config, top-5, impact по параметрам
│   └─ export_preset_yaml() → YAML для live-бота
│
└── АРТЕФАКТЫ → /data/backtest_results/
    ├─ {symbol}_optimization_report.json
    ├─ {symbol}_preset.yaml
    ├─ {symbol}_stress_test_results.json
    └─ batch_summary.csv
```

### 3.2 Ядро симуляции (GridBacktestSimulator)

```
GridBacktestSimulator.run_async(candles: DataFrame) → GridBacktestResult

  ИНИЦИАЛИЗАЦИЯ:
  ├─ market = MarketSimulator(balance, maker_fee, taker_fee)
  ├─ order_mgr = GridOrderManager()
  ├─ risk_mgr = GridRiskManager()
  └─ initial_orders = order_mgr.calculate_initial_orders(config, first_price)
      └─ market.create_order(order) для каждого уровня

  ─────────────────────────────────────────────────────────
  ОСНОВНОЙ ЦИКЛ (по каждой свече):
  ─────────────────────────────────────────────────────────
  for idx, candle in enumerate(candles):

    1. SWEEP ЦЕН ВНУТРИ СВЕЧИ
       prices = [open, low, high, close]   ← внутрисвечная гранулярность
       for price in prices:
           market.set_price(price)

    2. МАТЧИНГ ОРДЕРОВ (мгновенно)
       _check_limit_orders()
       ├─ buy_order.price >= current_price → FILL
       └─ sell_order.price <= current_price → FILL
       trade_history.append({...})
       balance.quote -= cost + fee
       balance.base += amount

    3. КОНТР-ОРДЕРА
       for new_trade in filled_trades:
           counter = order_mgr.on_order_filled(trade)
               └─ GridCycle: buy→sell или sell→buy
               └─ counter.price = filled.price + profit_per_grid
           market.create_order(counter)

    4. МЕТРИКИ
       equity = market.get_portfolio_value()     ← base * price + quote
       equity_curve.append((ts, equity))
       drawdown = (peak - equity) / peak

    5. РИСК-ПРОВЕРКИ
       action = risk_mgr.evaluate_risk(price, equity, pnl)
       ├─ stop_loss:    price < entry - loss%  → STOP
       ├─ max_drawdown: equity < peak * (1 - max_dd%) → STOP
       └─ take_profit:  pnl_pct >= target%     → STOP
       if action == STOP: break

    6. TRAILING GRID (опционально)
       if config.trailing_enabled:
           trailing_mgr.check_and_shift(price)
               ├─ if price > upper * (1 + shift_threshold): recenter up
               ├─ Отменить старые ордера
               └─ Разместить новые ордера на новых уровнях
  ─────────────────────────────────────────────────────────

  ФИНАЛЬНЫЙ РАСЧЁТ МЕТРИК
  └─ return GridBacktestResult {metrics, equity_curve, trade_history}
```

### 3.3 Оптимизатор (GridOptimizer)

```
GridOptimizer.optimize(config, candles, preset, objective)

  _generate_coarse_combos(preset, steps=3):
  └─ Cartesian product:
      spacing × linspace(levels_range, steps) × linspace(profit, steps) × linspace(amount, steps)
      = 2 × 3 × 3 × 3 = 54 комбинации (пример)

  _run_trials(combos, candles, objective, max_workers):
  └─ ProcessPoolExecutor(max_workers):
      futures = [pool.submit(_run_single_trial, config, candles) for config in combos]
      for future in as_completed(futures):
          trial = OptimizationTrial(objective_value=result[objective])

  _generate_fine_combos(best_coarse, preset, steps=3):
  └─ Уже 27 комбинаций вокруг лучшего coarse-результата

  Objectives: ROI | Sharpe | Calmar | ProfitFactor
  Checkpoint: OptimizationCheckpoint — сохранение прогресса при перезапуске
```

### 3.4 Классификатор монет (CoinClusterizer)

```
CoinClusterizer.classify(symbol, candles) → CoinProfile

  ATR% = avg(True Range) / avg(Close) * 100

  Кластеры:
  ├─ STABLE:      ATR% < 0.5
  ├─ BLUE_CHIPS:  0.5 ≤ ATR% < 2.0
  ├─ MID_CAPS:    2.0 ≤ ATR% < 5.0
  └─ MEMES:       ATR% ≥ 5.0

  ClusterPreset (параметры оптимизации):
  ├─ BLUE_CHIPS:  levels 10-20, profit 0.3%-0.8%, arithmetic+geometric
  ├─ MID_CAPS:    levels  8-15, profit 0.5%-1.5%, ...
  ├─ MEMES:       levels  5-10, profit 1.0%-3.0%, geometric
  └─ STABLE:      levels 15-25, profit 0.2%-0.5%, arithmetic
```

### 3.5 Вспомогательные компоненты

```
MarketSimulator (core/market_simulator.py)
├─ current_price, orders{}, balance, trade_history
├─ set_price(price)    → trigger _check_limit_orders()
├─ create_order(...)   → добавить в книгу ордеров
└─ get_portfolio_value() → base * price + quote

GridOrderManager (core/order_manager.py)
├─ Жизненный цикл ордеров: pending → filled
├─ on_order_filled() → генерировать контр-ордер
├─ GridCycle трекинг (buy @ level N → sell @ level N+profit)
└─ Переиспользует bot/strategies/grid/grid_order_manager.py

GridRiskManager (core/risk_manager.py)
├─ stop_loss_check(price)
├─ max_drawdown_check(equity, peak)
├─ take_profit_check(total_pnl_pct)
└─ Returns: RiskAction {HOLD, WARN, STOP_LOSS, DEACTIVATE}

GridCalculator (core/calculator.py)
├─ Расчёт уровней: арифметическое / геометрическое деление
├─ ATR расчёт (14-period SMA True Range)
├─ Авто-границы: upper/lower = ATR * multiplier от цены
└─ Переиспользует bot/strategies/grid/grid_calculator.py

TrailingGridManager (trailing/manager.py)
├─ Сдвиг сетки при выходе цены за threshold
├─ Режимы: ATR-based / fixed recenter
└─ Cooldown (защита от флип-флопа)

GridBacktestReporter (engine/reporter.py)
├─ generate_optimization_report() → {best_config, top-5, param_impact}
└─ export_preset_yaml() → YAML файл для live-бота
```

---

## 4. Multi-Strategy Backtesting Framework

### 4.1 Pipeline V1 (5 фаз) — scripts/run_dca_tf_smc_pipeline.py

```
Phase 1: BASELINE (завершено)
├─ Одиночный прогон каждой стратегии без оптимизации
├─ 45 пар × 3 стратегии (DCA, TF, SMC) = 135 задач
└─ Результат: phase1_baseline.json

Phase 2: OPTIMIZATION
├─ Grid-search параметров для DCA и TrendFollower
└─ Параллелизм: ProcessPoolExecutor (max_workers)

Phase 3: STRESS TESTING
└─ Запуск лучших конфигов на самых волатильных периодах

Phase 4: WALK-FORWARD ANALYSIS
└─ Скользящая оптимизация (IS) + валидация (OOS)

Phase 5: PARAMETER SENSITIVITY + MONTE CARLO
└─ Оценка устойчивости параметров к шуму
```

### 4.1b Pipeline V2.0 — scripts/run_backtest_v2.py

```
Phase 1: BASELINE (OrchestratorBacktestEngine, без оптимизации)
├─ BacktestOrchestratorEngine.run(data, cfg) для каждой пары
└─ Результат: phase1_orchestrator.json

Phase 2: OPTIMIZATION (ParameterOptimizer.optimize_orchestrator)
├─ Unified param_grid: router_cooldown_bars, dca_*, tf_*, risk_*
└─ Результат: best_params per-pair

Phase 3: PORTFOLIO (PortfolioBacktestEngine с лучшими параметрами)
├─ Одновременный бэктест N пар, общий капитал
└─ Результат: portfolio_result.json

Phase 4: ROBUSTNESS (Walk-Forward + Stress + Monte Carlo)
└─ Оценка устойчивости к разным периодам и шуму
```

### 4.2 Движок multi-timeframe (MultiTimeframeBacktestEngine)

```
MultiTimeframeBacktestEngine.run(strategy: BaseStrategy, data: MultiTimeframeData)

  for each M5 candle (мельчайшая гранулярность):

    1. Построить rolling DataFrame для D1, H4, H1, M15, M5

    2. [Опционально] Фильтр рыночного режима:
       regime = MarketRegimeDetector.analyze(df_h1)
       if strategy_type not in REGIME_ALLOWED[regime]: continue

    3. strategy.analyze_market(df_d1, df_h4, df_h1, df_m15)
       → BaseMarketAnalysis

    4. strategy.generate_signal(df_m15, balance)
       → BaseSignal | None

    5. if signal:
       ├─ [Опционально] risk_manager.evaluate()
       └─ strategy.open_position(signal, size)

    6. strategy.update_positions(current_price, df_m15)
       └─ if exit: strategy.close_position(id, reason, price)
           └─ TradeRecord → trade_history

    7. equity_curve.append({ts, equity, drawdown})

  return BacktestResult {metrics, trade_history, equity_curve, regime_history}
```

### 4.3 Компоненты V1

```
DCABacktester (bot/strategies/dca/dca_backtester.py)
└─ Симуляция жизненного цикла DCA-сделки: entry → safety orders → exit

ParameterOptimizer (bot/tests/backtesting/optimization.py)
├─ two_phase_optimize()     — Grid search + random search (V1)
├─ optimize_orchestrator()  — Unified grid-search для OrchestratorBacktestConfig (V2.0)
│   └─ _apply_orchestrator_params(): prefix-routing (dca_*, tf_*, grid_*, smc_*)
└─ Параллелизм: asyncio.gather() + ProcessPoolExecutor

StressTester (bot/tests/backtesting/stress_testing.py)
└─ Поиск волатильных периодов (volatility > threshold) + бэктест

WalkForwardAnalysis (bot/tests/backtesting/walk_forward.py)
└─ Скользящие окна: 3 мес train → 1 мес test → метрики IS vs OOS

MonteCarloAnalysis (bot/tests/backtesting/monte_carlo.py)
└─ Перетасовка порядка сделок → распределение исходов

SensitivityAnalysis (bot/tests/backtesting/sensitivity.py)
└─ Изменение параметра на ±X% → влияние на метрики
```

---

## 4b. Backtesting V2.0 — Orchestrator + Portfolio

### 4b.1 StrategyRouter (bot/tests/backtesting/strategy_router.py)

Зеркало `BotOrchestrator._update_active_strategies()` для бэктеста:

```
_REGIME_TO_STRATEGIES:
    GRID:            {"grid"}
    DCA:             {"dca"}
    HYBRID:          {"grid", "dca"}
    HOLD:            {}
    REDUCE_EXPOSURE: {}
    → BULL_TREND + enable_trend_follower: добавить "trend_follower"
    → BULL_TREND + enable_smc:            добавить "smc"

StrategyRouter(cooldown_bars=60, enable_trend_follower=True, enable_smc=False)
│
├── on_bar(regime: RegimeAnalysis | None, current_bar: int) → StrategyRouterEvent
│   ├─ regime=None → вернуть bootstrap-набор без записи в историю
│   ├─ Вычислить target_set по _REGIME_TO_STRATEGIES
│   ├─ if current_bar - _last_switch_bar < cooldown_bars: заблокировать
│   └─ иначе: обновить _active_strategies, записать в switch_history
│
├── .switch_history: list[dict]  — [{bar, from, to, regime}]
└── .reset()  — сбросить в bootstrap-состояние

StrategyRouterEvent:
    active_strategies: set[str]
    activated: set[str]
    deactivated: set[str]
    cooldown_remaining: int
```

Bootstrap-состояние: `{"grid", "dca", "trend_follower", "smc"}` — первый `on_bar()` всегда переключает к реальному набору.

### 4b.2 BacktestOrchestratorEngine (bot/tests/backtesting/orchestrator_engine.py)

```
OrchestratorBacktestConfig:
    symbol: str = "BTC/USDT"
    initial_balance: Decimal = 10000
    warmup_bars: int = 14400
    enable_grid/dca/trend_follower: bool = True
    enable_smc: bool = False
    enable_strategy_router: bool = True
    router_cooldown_bars: int = 60
    regime_check_every_n: int = 12      # 12 M5-баров = 1 час
    grid_params/dca_params/tf_params/smc_params: dict = {}
    enable_risk_manager: bool = True
    max_position_size_pct: float = 0.25
    max_daily_loss_pct: float = 0.05

BacktestOrchestratorEngine
├─ register_strategy_factory(name, factory_fn) — factory(params) → BaseStrategy
├─ run(data: MultiTimeframeData, config: OrchestratorBacktestConfig) → OrchestratorBacktestResult
│   ЦИКЛ (каждый M5-бар после warmup):
│   1. Каждые regime_check_every_n баров: MarketRegimeDetector.analyze(df_h1)
│   2. strategy_router.on_bar(regime, bar_idx) → active_set
│   3. Для каждой активной стратегии:
│      ├─ strategy.generate_signal(df, balance) → signal | None
│      ├─ risk_manager.check_trade(value, ...) → OK/REJECT
│      └─ strategy.open_position(signal, size) / update_positions()
│   4. Обновить equity_curve
│   └─ Собрать OrchestratorBacktestResult

OrchestratorBacktestResult(BacktestResult):
    strategy_switches: list[dict]       # [{bar, from_strategies, to_strategies, regime}]
    per_strategy_pnl: dict[str, float]  # {'grid': .., 'dca': .., 'trend_follower': ..}
    regime_routing_stats: dict          # сколько баров каждый режим
    cooldown_events: int                # сколько раз cooldown заблокировал переключение
    to_dict() → включает секцию "orchestrator"
```

### 4b.3 PortfolioBacktestEngine (bot/tests/backtesting/portfolio_engine.py)

```
PortfolioBacktestConfig:
    symbols: list[str]
    initial_capital: Decimal
    max_single_pair_pct: float = 0.25
    max_total_exposure_pct: float = 0.80
    portfolio_stop_loss_pct: float = 0.15
    per_pair_config: OrchestratorBacktestConfig  # шаблон

PortfolioBacktestEngine
└─ run(data_map: dict[str, MultiTimeframeData], config) → PortfolioBacktestResult
    ├─ per_pair_capital = initial_capital * min(max_single_pair_pct, 1/n_pairs)
    ├─ asyncio.gather() — параллельный запуск BacktestOrchestratorEngine для каждой пары
    └─ Агрегация метрик

PortfolioBacktestResult:
    per_pair_results: dict[str, OrchestratorBacktestResult]
    portfolio_total_return_pct: float
    portfolio_sharpe: float
    portfolio_max_drawdown_pct: float
    portfolio_equity_curve: list[dict]
    pair_correlation_matrix: dict[str, dict[str, float]]  # Pearson
    avg_pair_correlation: float
    best_pair: str
    worst_pair: str
    pairs_profitable: int
    to_dict() → полный JSON-отчёт
```

### 4b.4 Unified param_grid для optimize_orchestrator

```python
ORCHESTRATOR_PARAM_GRID = {
    # Маршрутизатор
    "router_cooldown_bars": [30, 60, 120],
    "regime_check_every_n": [6, 12, 24],
    # DCA (prefix dca_ → dca_params)
    "dca_trigger_pct": [0.03, 0.05, 0.07],
    "dca_tp_pct": [0.05, 0.08, 0.10],
    # TrendFollower (prefix tf_ → tf_params)
    "tf_ema_fast": [10, 15, 20],
    "tf_tp_atr_mult": [1.5, 2.0, 2.5],
    # Risk (top-level поля)
    "max_position_size_pct": [0.15, 0.20, 0.25],
}
```

---

## 5. Модели данных

### 5.1 GridBacktestConfig

```python
@dataclass
class GridBacktestConfig:
    symbol: str
    timeframe: str

    # Grid параметры
    upper_price: Decimal
    lower_price: Decimal
    num_levels: int
    spacing: GridSpacing       # ARITHMETIC | GEOMETRIC
    profit_per_grid: Decimal
    amount_per_grid: Decimal

    # Авто-границы
    atr_period: int = 14
    atr_multiplier: Decimal = Decimal("3.0")

    # Риск
    stop_loss_pct: Decimal
    max_drawdown_pct: Decimal
    take_profit_pct: Decimal

    # Trailing
    trailing_enabled: bool = False
    trailing_shift_threshold_pct: Decimal
    trailing_recenter_mode: str       # "atr" | "fixed"
```

### 5.2 GridBacktestResult

```python
@dataclass
class GridBacktestResult:
    # Доходность
    total_return_pct: float
    total_pnl: float
    final_equity: float

    # Риск
    max_drawdown_pct: float

    # Grid-специфичное
    completed_cycles: int
    grid_fill_rate: float          # уровней задействовано / всего уровней
    avg_profit_per_cycle: float
    capital_efficiency: float      # среднее задействованного / initial_balance

    # Risk-adjusted метрики
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    profit_factor: float

    # Временные ряды
    equity_curve: list[EquityPoint]
    trade_history: list[GridTradeRecord]

    # Мета
    candles_processed: int
    stopped_by_risk: bool
    stop_reason: str
```

### 5.3 BacktestResult (multi-strategy)

```python
@dataclass
class BacktestResult:
    strategy_name: str
    symbol: str

    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal | None
    win_rate: Decimal
    profit_factor: Decimal | None

    total_trades: int
    winning_trades: int
    avg_profit_per_trade: Decimal

    regime_history: list[dict]       # история смены режимов
    risk_manager_blocks: int          # сколько сигналов заблокировано риском
    risk_halted: bool

    trade_history: list[dict]
    equity_curve: list[dict]
```

### 5.4 OrchestratorBacktestResult (V2.0, расширяет BacktestResult)

```python
@dataclass
class OrchestratorBacktestResult(BacktestResult):
    # V2.0 extensions
    strategy_switches: list[dict]       # [{bar, from_strategies, to_strategies, regime}]
    per_strategy_pnl: dict[str, float]  # {'grid': .., 'dca': .., 'trend_follower': ..}
    regime_routing_stats: dict          # {regime_name: bars_count}
    cooldown_events: int                # сколько раз cooldown блокировал переключение
    initial_balance: Decimal
    final_balance: Decimal

    def to_dict() → dict:              # включает секцию "orchestrator"
```

### 5.4 MultiTimeframeData

```python
@dataclass
class MultiTimeframeData:
    symbol: str
    m5:  pd.DataFrame     # мельчайший таймфрейм (итерация)
    m15: pd.DataFrame
    h1:  pd.DataFrame
    h4:  pd.DataFrame
    d1:  pd.DataFrame
```

---

## 6. Метрики и формулы

| Метрика              | Формула |
|----------------------|---------|
| **Total Return %**   | `(final_equity - initial) / initial * 100` |
| **Max Drawdown %**   | `max((peak - equity) / peak)` для каждой точки |
| **Sharpe Ratio**     | `(mean_return / std_return) * √8760` (годовой, 1h свечи) |
| **Sortino Ratio**    | `(mean_return / downside_std) * √8760` |
| **Calmar Ratio**     | `annual_return_pct / max_drawdown_pct` |
| **Profit Factor**    | `gross_profit / abs(gross_loss)` |
| **Win Rate**         | `winning_cycles / total_cycles` |
| **Grid Fill Rate**   | `unique_levels_touched / total_levels` |
| **Capital Efficiency** | `avg(deployed_per_candle) / (initial * num_candles)` |

---

## 7. Персистентность

```
services/backtesting/data/
├── jobs.db      (SQLite, aiosqlite)
│   └─ JobStore: job_id, status, config_json, result_json, timestamps
│       API: create(), update_status(), get()
│
├── presets.db   (SQLite)
│   └─ PresetStore: symbol, config_yaml, cluster, metrics
│       API: create(), get_for_symbol()
│
└── checkpoints/ (OptimizationCheckpoint)
    └─ Сохранение выполненных trials при перезапуске (hash-дедупликация)

/data/backtest_results/{batch_id}/
├── {symbol}_optimization_report.json
├── {symbol}_preset.yaml
├── {symbol}_stress_test_results.json
└── batch_summary.csv
```

---

## 8. FastAPI (services/backtesting/src/grid_backtester/api/)

```
POST /api/v1/backtest/run
└─ → 202 Accepted {job_id} → background: GridBacktestSimulator.run()

GET  /api/v1/backtest/{job_id}
└─ → {status, result, error_message}

POST /api/v1/optimize/run
└─ → 202 Accepted {job_id} → background: GridOptimizer.optimize()

GET  /api/v1/presets
└─ → List[Preset] из PresetStore

GET  /api/v1/chart/{job_id}
└─ → HTMLResponse с Plotly-графиком (GridChartGenerator)

GET  /health
└─ → {"status": "healthy"}
```

---

## 9. Стек технологий

| Компонент            | Технология                         |
|----------------------|------------------------------------|
| Язык                 | Python 3.12                        |
| Web-фреймворк        | FastAPI + uvicorn                  |
| Данные               | Pandas, NumPy                      |
| Параллелизм          | ProcessPoolExecutor (CPU-bound)    |
| БД                   | SQLite + aiosqlite (async)         |
| Визуализация         | Plotly                             |
| Логирование          | structlog                          |
| Тесты                | Pytest, pytest-asyncio             |
| Деплой               | Docker Compose (standalone service)|

---

## 10. Известный архитектурный долг

| Проблема | Статус |
|----------|--------|
| Phase 2 V1 без смарт-направления — ~24 часа вычислений | ✅ V2.0 решает через `optimize_orchestrator()` с unified param_grid |
| SMC показывает отрицательный Sharpe по всем парам | ✅ Исправлен: `swing_length` 50→10 по умолчанию, warmup_bars динамический |
| "Insufficient data for structure analysis" в SMC | ✅ Исправлен через динамический `warmup_bars = max(swing_length*4, 100)` |
| MarketRegimeDetector в бэктесте — не включена | ✅ Включена в V2.0: `StrategyRouter` активирует/деактивирует стратегии по режиму |
| 7 пар отсутствуют (NEAR, APT, PEPE, WIF, BONK, SUI, SEI) | Нужно скачать исторические данные |
| Индикаторы пересчитываются для каждого trial | Нужен кэш в Parquet для ускорения |
| PortfolioBacktestEngine: нет реальной синхронизации капитала по времени | Каждая пара независима; PortfolioRiskManager не интегрирован в backtest loop |
