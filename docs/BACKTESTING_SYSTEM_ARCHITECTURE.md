# TRADERAGENT v2.0 — Unified Backtesting System Architecture

## 1. Проблема

Текущая система бэктестинга поддерживает **только Grid-стратегию**. Но для v2.0 нужно тестировать:

- Все 5 стратегий по отдельности
- Переключения между стратегиями (режим рынка меняется)
- Портфельные комбинации (несколько пар с разными стратегиями)
- SMC Filter как энхансер
- Capital Allocator и Risk Aggregator

**Цель:** единый фреймворк бэктестинга, который может валидировать весь алгоритм v2.0 на исторических данных до запуска в продакшен.

---

## 2. Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                   BACKTESTING FRAMEWORK v2.0                     │
│                                                                 │
│  ┌───────────┐   ┌─────────────┐   ┌──────────────────────┐    │
│  │  Data      │   │  Simulation │   │  Analysis &          │    │
│  │  Pipeline  │──→│  Engine     │──→│  Reporting           │    │
│  │            │   │             │   │                      │    │
│  └───────────┘   └─────────────┘   └──────────────────────┘    │
│       │                │                      │                  │
│       ▼                ▼                      ▼                  │
│  ┌───────────┐   ┌─────────────┐   ┌──────────────────────┐    │
│  │ Historical │   │  Strategy   │   │  Equity Curves       │    │
│  │ OHLCV Data │   │  Adapters   │   │  Trade Journal       │    │
│  │ 450 CSVs   │   │  (5 types)  │   │  Metrics Dashboard   │    │
│  │ 5.4 GB     │   │             │   │  Optimization Report │    │
│  └───────────┘   └─────────────┘   └──────────────────────┘    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              OPTIMIZATION ENGINE                      │       │
│  │  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │       │
│  │  │  Single   │  │  Multi   │  │  Walk-Forward     │  │       │
│  │  │  Strategy │  │  Strategy│  │  Validation       │  │       │
│  │  └──────────┘  └──────────┘  └───────────────────┘  │       │
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Pipeline — Подготовка данных

### 3.1. Источники данных

```
Имеющиеся данные:
  450 CSV файлов, 5.4 GB
  45 торговых пар × 10 таймфреймов (5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d)
  Глубина: до 7.8 лет (BTC), минимум 2 года (HNT)

Структура CSV:
  timestamp, open, high, low, close, volume
```

### 3.2. DataLoader

```python
class BacktestDataLoader:
    """Загружает и подготавливает исторические данные."""

    def load_pair(self, symbol: str, timeframe: str,
                  start: datetime, end: datetime) -> pd.DataFrame:
        """Загрузить OHLCV для одной пары."""

    def load_multi_timeframe(self, symbol: str,
                              timeframes: list[str]) -> dict[str, pd.DataFrame]:
        """Загрузить несколько таймфреймов (для SMC и Trend Follower)."""

    def precompute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Предрассчитать индикаторы: EMA, ADX, ATR, RSI, BB, Volume ratio.
        Выполняется один раз, результат кешируется."""

    def split_windows(self, df: pd.DataFrame,
                      window_months: int = 3,
                      overlap_pct: float = 0.0) -> list[pd.DataFrame]:
        """Разбить на окна для Walk-Forward анализа."""
```

### 3.3. Кеширование индикаторов

Индикаторы рассчитываются **один раз** при загрузке и сохраняются в `.parquet`:

```
data/
├── raw/                          # Оригинальные CSV
│   ├── BTCUSDT_1h.csv
│   └── ...
├── indicators/                   # Предрассчитанные индикаторы
│   ├── BTCUSDT_1h_indicators.parquet
│   └── ...
└── cache/                        # Промежуточные результаты оптимизации
    └── ...
```

Это решает баг из Session 10: «параллельный оптимизатор кешировал индикаторы между воркерами некорректно».

---

## 4. Simulation Engine — Движок симуляции

### 4.1. Универсальный симулятор

Текущий `GridBacktestSimulator` заменяется на **универсальный**:

```python
class UniversalSimulator:
    """Единый симулятор для всех стратегий."""

    def __init__(self, config: SimulationConfig):
        self.exchange = SimulatedExchange(config)
        self.strategy: BaseBacktestStrategy = None
        self.smc_filter: SMCBacktestFilter = None
        self.risk_manager = BacktestRiskManager(config)
        self.journal = TradeJournal()

    def run(self, data: pd.DataFrame) -> BacktestResult:
        """Главный цикл симуляции."""
        for i, candle in data.iterrows():
            # 1. Обновить SimulatedExchange (исполнить pending orders)
            self.exchange.process_candle(candle)

            # 2. Получить сигнал от стратегии
            signal = self.strategy.evaluate(candle, self.exchange.state)

            # 3. Пропустить через SMC Filter (если включён)
            if self.smc_filter and signal:
                signal = self.smc_filter.filter(signal, candle)

            # 4. Risk check
            if signal and self.risk_manager.allow(signal):
                self.exchange.execute(signal)

            # 5. Записать состояние
            self.journal.record(candle, self.exchange.state)

        return self.journal.to_result()
```

### 4.2. SimulatedExchange — Имитация биржи

```python
class SimulatedExchange:
    """Реалистичная симуляция биржевого исполнения."""

    def __init__(self, config: SimulationConfig):
        self.balance = config.initial_capital
        self.positions: dict[str, Position] = {}
        self.pending_orders: list[Order] = []
        self.filled_orders: list[Order] = []
        self.fee_rate = config.fee_rate           # default: 0.075% (Bybit taker)
        self.slippage_model = config.slippage      # "none" | "fixed" | "volume_based"

    def process_candle(self, candle: pd.Series):
        """Проверяет исполнение pending orders по high/low свечи."""
        for order in self.pending_orders:
            if order.side == "buy" and candle.low <= order.price:
                self._fill(order, fill_price=order.price, candle=candle)
            elif order.side == "sell" and candle.high >= order.price:
                self._fill(order, fill_price=order.price, candle=candle)

    def _fill(self, order, fill_price, candle):
        """Исполнить ордер с учётом комиссии и проскальзывания."""
        slippage = self._calc_slippage(order, candle)
        actual_price = fill_price + slippage
        fee = abs(order.qty * actual_price) * self.fee_rate
        # Обновить balance, positions...
```

### 4.3. Модели проскальзывания

```python
class SlippageModel:
    """Три модели для разных уровней реализма."""

    @staticmethod
    def none(order, candle) -> float:
        """Идеальное исполнение. Для быстрых тестов."""
        return 0.0

    @staticmethod
    def fixed(order, candle, bps: float = 1.0) -> float:
        """Фиксированное проскальзывание в базисных пунктах."""
        return order.price * (bps / 10000)

    @staticmethod
    def volume_based(order, candle, impact: float = 0.1) -> float:
        """Проскальзывание пропорционально order_size / candle_volume."""
        participation = (order.qty * order.price) / (candle.volume * candle.close)
        return order.price * participation * impact
```

---

## 5. Strategy Adapters — Адаптеры стратегий

Каждая стратегия имеет бэктест-адаптер, реализующий единый интерфейс:

```python
class BaseBacktestStrategy(ABC):
    """Единый интерфейс для всех стратегий в бэктесте."""

    @abstractmethod
    def evaluate(self, candle: pd.Series, state: ExchangeState) -> Signal | None:
        """Получить торговый сигнал на основе текущей свечи."""

    @abstractmethod
    def get_parameter_space(self) -> dict[str, list]:
        """Вернуть пространство параметров для оптимизации."""

    @abstractmethod
    def from_params(self, params: dict) -> "BaseBacktestStrategy":
        """Создать экземпляр с указанными параметрами."""
```

### 5.1. Grid Adapter

```python
class GridBacktestAdapter(BaseBacktestStrategy):
    """Адаптер Grid-стратегии для бэктестинга.
    Переиспользует существующий GridCalculator и GridOrderManager."""

    params = {
        "num_levels": [8, 10, 12, 15, 20, 25, 30],
        "profit_per_grid": [0.001, 0.003, 0.005, 0.008, 0.01, 0.015],
        "grid_type": ["arithmetic", "geometric"],
        "range_factor": [1.0, 1.5, 2.0, 2.5],  # множитель ATR для диапазона
    }

    def evaluate(self, candle, state):
        # Проверить заполненные уровни
        # Разместить counter-orders
        # Detect cycle completion
```

### 5.2. DCA Adapter

```python
class DCABacktestAdapter(BaseBacktestStrategy):
    """Адаптер DCA-стратегии."""

    params = {
        "base_order_pct": [0.01, 0.02, 0.03],           # % капитала на базовый ордер
        "safety_order_pct": [0.02, 0.03, 0.05],          # % на safety order
        "safety_order_step": [0.01, 0.02, 0.03, 0.05],   # % падения для каждого SO
        "step_multiplier": [1.0, 1.2, 1.5, 2.0],         # множитель шага SO
        "volume_multiplier": [1.0, 1.3, 1.5, 2.0],       # множитель объёма SO
        "take_profit_pct": [0.005, 0.01, 0.015, 0.02],   # % TP от средней
        "max_safety_orders": [3, 5, 7, 10],
        "confluence_threshold": [0.4, 0.5, 0.6, 0.7],
    }

    def evaluate(self, candle, state):
        # Рассчитать confluence score (EMA, ADX, RSI, BB, Volume)
        # Если score >= threshold → сигнал на вход / safety order
        # Проверить TP / trailing stop
```

### 5.3. Trend Follower Adapter

```python
class TrendFollowerBacktestAdapter(BaseBacktestStrategy):
    """Адаптер Trend Follower."""

    params = {
        "ema_fast": [10, 12, 20],
        "ema_slow": [26, 50, 100],
        "atr_period": [14, 20],
        "atr_sl_multiplier": [1.5, 2.0, 2.5],
        "atr_tp_multiplier": [1.2, 1.5, 2.0, 2.5],
        "rsi_period": [14],
        "rsi_overbought": [70, 75],
        "rsi_oversold": [25, 30],
        "trend_confirmation_candles": [2, 3, 5],
    }

    def evaluate(self, candle, state):
        # Проверить EMA crossover (fast > slow = bullish)
        # Подтвердить RSI
        # Рассчитать SL/TP по ATR
        # Управлять trailing stop
```

### 5.4. Hybrid Adapter

```python
class HybridBacktestAdapter(BaseBacktestStrategy):
    """Адаптер Hybrid — автопереключение Grid/DCA в рамках бэктеста."""

    params = {
        "adx_threshold": [20, 25, 30],
        "grid_allocation_pct": [0.5, 0.6, 0.7],
        "dca_allocation_pct": [0.2, 0.3, 0.4],
        # + все параметры Grid и DCA
    }

    def evaluate(self, candle, state):
        # Определить режим по ADX
        # Делегировать Grid или DCA sub-adapter
```

### 5.5. SMC Filter Adapter

```python
class SMCBacktestFilter:
    """SMC как фильтр для бэктестинга. Работает поверх любой стратегии."""

    params = {
        "ob_lookback": [50, 100, 200],         # свечей для поиска Order Blocks
        "fvg_min_size_pct": [0.001, 0.003],    # минимальный размер FVG
        "min_confidence": [0.3, 0.4, 0.5],
        "enhanced_threshold": [0.6, 0.7, 0.8],
        "neutral_size_mult": [0.3, 0.5, 0.7],
    }

    def filter(self, signal: Signal, candle: pd.Series) -> Signal | None:
        # Проверить: сигнал совпадает с Order Block или FVG?
        # Вернуть: ENHANCED / NEUTRAL (уменьшенный) / REJECT (None)
```

---

## 6. Режимы бэктестинга

### 6.1. Single Strategy Backtest

Тестирует одну стратегию на одной паре:

```
Input:  BTC/USDT 1h, 2024-01-01 to 2025-12-31, Grid strategy
Output: ROI, Sharpe, Calmar, Max Drawdown, Win Rate, Trade Count
```

### 6.2. Multi-Strategy Backtest (НОВОЕ)

Тестирует переключение стратегий по режиму рынка — **это ключевое нововведение**:

```python
class MultiStrategyBacktest:
    """Симуляция полного алгоритма v2.0 на исторических данных."""

    def run(self, data: pd.DataFrame, pair: str) -> BacktestResult:
        regime_classifier = RegimeClassifier()
        strategy_router = StrategyRouter()
        current_strategy = None

        for i, candle in data.iterrows():
            # 1. Определить режим (как в Master Loop)
            regime = regime_classifier.classify(candle)

            # 2. Выбрать стратегию
            target_strategy = strategy_router.route(regime)

            # 3. Переключить если нужно (с гистерезисом)
            if target_strategy != current_strategy:
                if self._confirm_transition(regime):
                    self._graceful_transition(current_strategy, target_strategy)
                    current_strategy = target_strategy

            # 4. Выполнить стратегию
            signal = current_strategy.evaluate(candle, state)
            # ... SMC filter, risk check, execute
```

Это позволяет **сравнить**:
- "Всегда Grid" vs "Всегда DCA" vs "Адаптивное переключение"
- Найти оптимальные пороги переключения (ADX thresholds)
- Измерить стоимость ложных переключений (flip-flop)

### 6.3. Portfolio Backtest (НОВОЕ)

Тестирует весь портфель — несколько пар одновременно:

```python
class PortfolioBacktest:
    """Симуляция портфеля из нескольких пар с Capital Allocator."""

    def run(self, pairs: list[str], data: dict[str, pd.DataFrame]) -> PortfolioResult:
        allocator = CapitalAllocator(total_capital=100_000)
        risk_agg = PortfolioRiskAggregator()

        # Синхронизировать свечи по timestamp
        timeline = self._merge_timelines(data)

        for timestamp in timeline:
            # 1. Capital Allocation per pair
            allocations = allocator.allocate(pair_regimes, pair_performance)

            # 2. Per-pair strategy execution
            for pair in pairs:
                candle = data[pair].loc[timestamp]
                signal = strategies[pair].evaluate(candle, states[pair])

                # 3. Portfolio-level risk check
                if risk_agg.allow(signal, total_exposure):
                    execute(signal, allocations[pair])

            # 4. Portfolio metrics
            portfolio_equity.append(sum(pair_equities))
```

Это позволяет:
- Увидеть диверсификационный эффект (портфель vs отдельные пары)
- Протестировать корреляционные лимиты
- Найти оптимальное количество пар и аллокацию

---

## 7. Optimization Engine — Движок оптимизации

### 7.1. Трёхфазная оптимизация

```
Phase 1: Coarse Grid Search (грубый перебор)
  ─────────────────────────────────────
  Для каждого кластера (STABLE, BLUE_CHIPS, MID_CAPS, MEMES):
    Тестируем preset параметры из CoinClusterizer
    Метрика: ROI
    Результат: лучший preset для каждого кластера

Phase 2: Fine-Tuning (тонкая настройка)
  ──────────────────────────────────
  Вокруг лучшего preset из Phase 1:
    ±2 уровня для num_levels
    ±30% для profit_per_grid
    ±20% для ATR multipliers
  Метрика: Sharpe Ratio (баланс доходности и риска)
  Результат: оптимальные параметры per pair

Phase 3: Walk-Forward Validation (проверка устойчивости)
  ─────────────────────────────────────────────────
  Разбиваем историю на окна:
    ┌────────────┬──────────┐
    │ Train (70%)│ Test(30%)│  Window 1
    ├────────────┼──────────┤
    │    Train   │  Test    │  Window 2 (сдвиг на 30%)
    ├────────────┼──────────┤
    │    Train   │  Test    │  Window 3
    └────────────┴──────────┘

  Оптимизируем на Train, проверяем на Test
  Метрика: Стабильность Test-результата ≥ 70% от Train
  Результат: параметры, которые не переобучены
```

### 7.2. Параллельная обработка

```python
class ParallelOptimizer:
    """Параллельный оптимизатор с правильным кешированием."""

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or (os.cpu_count() - 1)

    async def optimize(self, strategy: BaseBacktestStrategy,
                       data: pd.DataFrame,
                       objective: str = "sharpe") -> OptimizationResult:

        param_combinations = self._generate_combinations(
            strategy.get_parameter_space()
        )

        # Каждый worker получает СВОЮ копию предрассчитанных индикаторов
        # (исправление бага из Session 10)
        indicator_cache = precompute_indicators(data)

        results = []
        with ProcessPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [
                pool.submit(
                    _run_single_backtest,
                    strategy_class=type(strategy),
                    params=params,
                    data=data,
                    indicators=indicator_cache,  # read-only copy
                    objective=objective,
                )
                for params in param_combinations
            ]

            for future in as_completed(futures):
                results.append(future.result())

        return self._rank_results(results, objective)
```

### 7.3. Objective Functions — Целевые функции

```python
OBJECTIVES = {
    "roi": lambda r: r.total_return_pct,

    "sharpe": lambda r: (
        r.total_return_pct / r.return_std
        if r.return_std > 0 else 0
    ),

    "calmar": lambda r: (
        r.annualized_return / abs(r.max_drawdown_pct)
        if r.max_drawdown_pct != 0 else 0
    ),

    "profit_factor": lambda r: (
        r.gross_profit / abs(r.gross_loss)
        if r.gross_loss != 0 else float('inf')
    ),

    # НОВОЕ: комбинированная метрика для v2.0
    "composite": lambda r: (
        0.3 * normalize(r.total_return_pct)     # доходность
        + 0.3 * normalize(r.sharpe_ratio)        # стабильность
        + 0.2 * normalize(r.win_rate)            # точность
        + 0.2 * normalize(-r.max_drawdown_pct)   # защита капитала
    ),
}
```

---

## 8. Reporting — Отчёты

### 8.1. BacktestResult — Стандартный результат

```python
@dataclass
class BacktestResult:
    # Идентификация
    strategy: str               # "grid" | "dca" | "trend" | "hybrid" | "multi"
    symbol: str                 # "BTC/USDT"
    timeframe: str              # "1h"
    period: tuple[datetime, datetime]

    # P&L
    initial_capital: Decimal
    final_capital: Decimal
    total_return_pct: float
    annualized_return: float
    total_fees_paid: Decimal

    # Risk
    max_drawdown_pct: float
    max_drawdown_duration: timedelta
    sharpe_ratio: float
    calmar_ratio: float
    sortino_ratio: float

    # Trading
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    avg_trade_duration: timedelta
    avg_win: Decimal
    avg_loss: Decimal
    max_consecutive_losses: int

    # Equity curve (для визуализации)
    equity_curve: list[tuple[datetime, Decimal]]
    drawdown_curve: list[tuple[datetime, float]]

    # Trades (для журнала)
    trades: list[TradeRecord]

    # Strategy-specific
    metadata: dict              # Grid: cycles, levels filled, etc.
                                # DCA: safety orders used, avg accumulation
                                # Trend: trends caught, false signals
```

### 8.2. Визуализация (Plotly)

```
Equity Curve Report
════════════════════

Chart 1: Equity Curve
  ┌──────────────────────────────────┐
  │    ╱╲      ╱╲    ╱╲ ╱╲          │  ← equity
  │   ╱  ╲    ╱  ╲  ╱  ╱  ╲ ╱──    │
  │  ╱    ╲  ╱    ╲╱  ╱    ╲╱      │
  │ ╱      ╲╱                       │
  │╱                                │
  └──────────────────────────────────┘
  Jan    Mar    May    Jul    Sep

Chart 2: Drawdown Underwater
  ┌──────────────────────────────────┐
  │──────╲    ╱──╲  ╱──────────╲  ╱─│
  │       ╲  ╱    ╲╱            ╲╱  │
  │        ╲╱                       │
  │                                 │
  │         -8.3% max DD            │
  └──────────────────────────────────┘

Chart 3: Monthly Returns Heatmap
  ┌────┬────┬────┬────┬────┬────┐
  │Jan │Feb │Mar │Apr │May │Jun │
  │+2.1│-0.5│+3.2│+1.8│+0.3│-1.1│
  │ 🟢 │ 🔴 │ 🟢 │ 🟢 │ 🟡 │ 🔴 │
  └────┴────┴────┴────┴────┴────┘

Chart 4: Strategy Switches (только для Multi-Strategy)
  ┌──────────────────────────────────┐
  │ GRID ████████░░ DCA ██████░░ TF █│
  │ (sideways)    (bear)    (bull)   │
  └──────────────────────────────────┘
```

### 8.3. Сравнительный отчёт

```
┌─────────────────────────────────────────────────────────────────┐
│              COMPARISON: BTC/USDT 2024-2025                      │
├──────────────┬──────┬──────┬──────┬──────┬──────────────────────┤
│ Metric       │ Grid │ DCA  │Trend │Hybrid│ Multi-Strategy (v2.0)│
├──────────────┼──────┼──────┼──────┼──────┼──────────────────────┤
│ ROI          │+8.2% │+12.1%│+18.5%│+14.3%│ +22.7%              │
│ Max Drawdown │-4.1% │-8.7% │-11.2%│-6.5% │ -7.3%               │
│ Sharpe       │ 1.82 │ 1.45 │ 1.21 │ 1.67 │  2.14               │
│ Win Rate     │ 78%  │ 65%  │ 52%  │ 71%  │  68%                │
│ Trades       │ 342  │  47  │  31  │ 189  │  198                │
│ Profit Factor│ 2.1  │ 1.8  │ 2.4  │ 2.0  │  2.6                │
├──────────────┴──────┴──────┴──────┴──────┴──────────────────────┤
│ Verdict: Multi-Strategy beats all single strategies              │
│ Best ROI with acceptable drawdown. SMC filter reduced            │
│ losing trades by 23% compared to raw signals.                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Интеграция с Web UI

### 9.1. API Endpoints

```
POST /api/v1/backtesting/run
  Body: {
    "mode": "single" | "multi_strategy" | "portfolio",
    "strategy": "grid" | "dca" | "trend" | "hybrid",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
    "params": { ... },                  // опционально: если нет — оптимизация
    "smc_filter": true,                 // включить SMC Enhancement
    "slippage_model": "volume_based",   // реалистичность
    "optimize": {
      "enabled": true,
      "objective": "composite",
      "walk_forward": true
    }
  }

GET /api/v1/backtesting/status/{job_id}
  Response: { "status": "running", "progress": 45, "eta_seconds": 120 }

GET /api/v1/backtesting/result/{job_id}
  Response: BacktestResult (JSON)

GET /api/v1/backtesting/compare
  Query: job_ids=1,2,3,4
  Response: Сравнительная таблица

POST /api/v1/backtesting/export-preset/{job_id}
  Response: YAML preset для продакшен-деплоя
```

### 9.2. WebSocket прогресс

```
WS /ws/backtesting/{job_id}
  Сообщения:
    {"type": "progress", "pct": 45, "current_date": "2024-06-15"}
    {"type": "trade", "side": "buy", "price": 65000, "qty": 0.01}
    {"type": "regime_change", "from": "GRID", "to": "DCA", "reason": "ADX=32"}
    {"type": "equity_update", "value": 102350.50}
    {"type": "complete", "result_id": "abc123"}
```

---

## 10. Полный Pipeline — Как запускать

### 10.1. Single Strategy Backtest

```bash
# Из CLI
python -m bot.backtesting.run \
  --strategy grid \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --optimize \
  --objective sharpe

# Результат: JSON + equity curve PNG + preset YAML
```

### 10.2. Multi-Strategy Comparison

```bash
python -m bot.backtesting.run \
  --mode compare \
  --symbol BTC/USDT \
  --timeframe 1h \
  --strategies grid,dca,trend,hybrid,multi \
  --start 2024-01-01 \
  --end 2025-12-31

# Результат: сравнительная таблица всех стратегий на одних данных
```

### 10.3. Portfolio Backtest

```bash
python -m bot.backtesting.run \
  --mode portfolio \
  --pairs BTC/USDT,ETH/USDT,SOL/USDT,DOGE/USDT,LINK/USDT \
  --timeframe 1h \
  --capital 100000 \
  --start 2024-01-01 \
  --end 2025-12-31

# Результат: портфельный equity curve, аллокации, корреляции
```

### 10.4. Batch Optimization (45 pairs)

```bash
python -m bot.backtesting.batch \
  --pairs-dir data/raw/ \
  --timeframe 1h \
  --window-months 6 \
  --strategies grid,dca,trend \
  --optimize \
  --output presets/

# Результат: per-pair optimal presets + summary report
# Время: ~30-45 минут на 4-core сервере
```

---

## 11. Файловая структура

```
bot/backtesting/
├── __init__.py
├── run.py                      # CLI entry point
├── batch.py                    # Batch processing 45 pairs
│
├── core/
│   ├── simulator.py            # UniversalSimulator
│   ├── exchange.py             # SimulatedExchange
│   ├── slippage.py             # SlippageModel
│   ├── journal.py              # TradeJournal
│   └── result.py               # BacktestResult dataclass
│
├── adapters/
│   ├── base.py                 # BaseBacktestStrategy (ABC)
│   ├── grid_adapter.py         # GridBacktestAdapter
│   ├── dca_adapter.py          # DCABacktestAdapter
│   ├── trend_adapter.py        # TrendFollowerBacktestAdapter
│   ├── hybrid_adapter.py       # HybridBacktestAdapter
│   └── smc_filter.py           # SMCBacktestFilter
│
├── multi/
│   ├── multi_strategy.py       # MultiStrategyBacktest
│   ├── portfolio.py            # PortfolioBacktest
│   ├── regime_classifier.py    # RegimeClassifier for backtest
│   └── capital_allocator.py    # CapitalAllocator simulation
│
├── optimization/
│   ├── optimizer.py            # ParallelOptimizer
│   ├── walk_forward.py         # Walk-Forward Validation
│   └── objectives.py           # Objective functions
│
├── data/
│   ├── loader.py               # BacktestDataLoader
│   └── indicator_cache.py      # Precomputed indicators (.parquet)
│
├── reporting/
│   ├── charts.py               # Plotly equity curves, heatmaps
│   ├── comparison.py           # Multi-strategy comparison
│   └── preset_export.py        # YAML preset generation
│
└── api/
    ├── routes.py               # FastAPI endpoints
    └── websocket.py            # Real-time progress updates
```

---

## 12. Связь с продакшеном

```
                    BACKTESTING                     PRODUCTION
                    ═══════════                     ══════════

  ┌──────────────┐                    ┌──────────────────────┐
  │  Optimize    │                    │  Live Trading        │
  │  Parameters  │──→ YAML Preset ──→│  Load Preset         │
  │              │                    │                      │
  │  Walk-Forward│                    │  Master Loop         │
  │  Validated   │                    │  uses same:          │
  │              │                    │  • RegimeClassifier   │
  │  Shared Core:│                    │  • StrategyRouter     │
  │  GridCalc    │◄─── same code ───→│  • GridCalculator     │
  │  DCAEngine   │                    │  • DCAEngine          │
  │  TrendLogic  │                    │  • TrendFollower      │
  └──────────────┘                    └──────────────────────┘

  Ключевой принцип: один и тот же код стратегий используется
  и в бэктесте, и в продакшене. Отличается только exchange layer.
```

Результат оптимизации — YAML preset — напрямую загружается в продакшен:

```yaml
# presets/BTCUSDT_optimized.yaml
symbol: BTC/USDT
strategy: multi_strategy
optimized_at: "2026-02-20"
walk_forward_validated: true
test_period: "2024-01-01 to 2025-12-31"

regime_thresholds:
  adx_enter_trend: 32
  adx_exit_trend: 25
  confirmation_candles: 3
  min_regime_duration_hours: 4

grid_params:
  num_levels: 15
  profit_per_grid: 0.005
  grid_type: arithmetic
  range_factor: 2.0

dca_params:
  safety_order_step: 0.03
  step_multiplier: 1.5
  volume_multiplier: 1.5
  take_profit_pct: 0.015
  max_safety_orders: 7

trend_params:
  ema_fast: 20
  ema_slow: 50
  atr_sl_multiplier: 2.0
  atr_tp_multiplier: 2.5

smc_filter:
  enabled: true
  min_confidence: 0.4
  enhanced_threshold: 0.7
  neutral_size_mult: 0.5

performance:
  roi: 22.7%
  sharpe: 2.14
  max_drawdown: -7.3%
  win_rate: 68%
```
