# TRADERAGENT v2.0 — Unified Backtesting System Architecture

## 1. Проблема

Текущая система бэктестинга поддерживает **только Grid-стратегию**. Но для v2.0 нужно тестировать:

- Все 3 стратегии по отдельности (Grid, DCA, Trend Follower)
- Адаптивное переключение между стратегиями (режим рынка меняется)
- Портфельные комбинации (несколько пар с разными стратегиями)
- SMC Filter как энхансер с трекингом зон
- Capital Allocator с нормализацией и committed/available capital
- Risk Aggregator с 3-уровневой защитой, Emergency Halt, STRESS_MODE

> **Примечание:** HYBRID удалён как отдельная стратегия (см. TRADERAGENT_V2_ALGORITHM.md,
> раздел 4.1). Его функция переключения Grid/DCA теперь выполняется Strategy Router'ом.
> Multi-Strategy Backtest полностью покрывает сценарий HYBRID.

**Цель:** единый фреймворк бэктестинга, который может валидировать весь алгоритм v2.0 — включая переключения, аллокацию и риск-менеджмент — на исторических данных до запуска в продакшен.

---

## 2. Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   BACKTESTING FRAMEWORK v2.0                             │
│                                                                         │
│  ┌───────────┐   ┌──────────────────┐   ┌──────────────────────┐       │
│  │  Data      │   │  Simulation      │   │  Analysis &          │       │
│  │  Pipeline  │──→│  Engine          │──→│  Reporting           │       │
│  │            │   │                  │   │                      │       │
│  └───────────┘   └──────────────────┘   └──────────────────────┘       │
│       │                │                        │                       │
│       ▼                ▼                        ▼                       │
│  ┌───────────┐   ┌──────────────────┐   ┌──────────────────────┐       │
│  │ Historical │   │  Strategy        │   │  Equity Curves       │       │
│  │ OHLCV Data │   │  Adapters        │   │  Trade Journal       │       │
│  │ 450 CSVs   │   │  (3 strategies   │   │  Transition Log      │       │
│  │ 5.4 GB     │   │   + SMC filter)  │   │  Halt Events         │       │
│  └───────────┘   └──────────────────┘   │  Correlation Report   │       │
│                                          └──────────────────────┘       │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │              OPTIMIZATION ENGINE                              │       │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐  │       │
│  │  │  Single   │  │  Multi    │  │ Portfolio│  │Walk-Forward│  │       │
│  │  │  Strategy │  │  Strategy │  │  Backtest│  │Validation  │  │       │
│  │  └──────────┘  └───────────┘  └──────────┘  └───────────┘  │       │
│  └──────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
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
        """Загрузить несколько таймфреймов (для SMC Filter: 1h + 4h)."""

    def precompute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Предрассчитать индикаторы: EMA(20,50), ADX(14), ATR(14), RSI(14), BB, Volume ratio.
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

Текущий `GridBacktestSimulator` заменяется на **универсальный** с поддержкой `SignalType`-маршрутизации:

> **Ключевое решение конфликта C1:** SMC Filter применяется ТОЛЬКО к сигналам типа `ENTRY`.
> Exit-сигналы (SL, TP, transition close) обходят фильтр. Grid counter-orders тоже обходят фильтр.

```python
class SignalType(Enum):
    """Тип сигнала определяет маршрут обработки."""
    ENTRY = "entry"                 # Вход → проходит SMC Filter
    EXIT_TP = "exit_tp"             # Take-Profit → обходит SMC
    EXIT_SL = "exit_sl"             # Stop-Loss → обходит SMC
    EXIT_TRANSITION = "exit_transition"  # Закрытие при смене стратегии → обходит SMC
    EXIT_EMERGENCY = "exit_emergency"    # Emergency Halt → обходит SMC
    GRID_COUNTER = "grid_counter"   # Grid counter-order → обходит SMC (часть цикла)


@dataclass
class Signal:
    """Торговый сигнал от стратегии."""
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal
    price: Decimal | None           # None = market order
    signal_type: SignalType
    strategy_source: str            # "grid" | "dca" | "trend"
    metadata: dict = field(default_factory=dict)


class UniversalSimulator:
    """Единый симулятор для всех стратегий с маршрутизацией сигналов."""

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
            fills = self.exchange.process_candle(candle)

            # 2. Обновить SMC-зоны (раз в N свечей, эмуляция Master Loop)
            if self.smc_filter and i % self.smc_filter.recalc_interval == 0:
                self.smc_filter.recalculate_zones(data, i)

            # 3. Обновить касания SMC-зон текущей ценой
            if self.smc_filter:
                self.smc_filter.update_touches(candle.close)

            # 4. Получить сигнал(ы) от стратегии
            signals = self.strategy.evaluate(candle, self.exchange.state)

            # 5. Маршрутизация каждого сигнала
            for signal in (signals if isinstance(signals, list) else [signals]):
                if signal is None:
                    continue
                signal = self._route_signal(signal, candle)
                if signal and self.risk_manager.allow(signal, self.exchange.state):
                    self.exchange.execute(signal)

            # 6. Записать состояние
            self.journal.record(candle, self.exchange.state)

        return self.journal.to_result()

    def _route_signal(self, signal: Signal, candle: pd.Series) -> Signal | None:
        """Маршрутизация сигнала через SMC Filter на основе SignalType."""

        # ТОЛЬКО entry-сигналы проходят через SMC
        if signal.signal_type == SignalType.ENTRY and self.smc_filter:
            return self.smc_filter.filter(signal, candle)

        # Все остальные типы — прямое исполнение без фильтрации:
        # EXIT_TP, EXIT_SL, EXIT_TRANSITION, EXIT_EMERGENCY, GRID_COUNTER
        return signal
```

### 4.2. SimulatedExchange — Имитация биржи

```python
class SimulatedExchange:
    """Реалистичная симуляция биржевого исполнения
    с трекингом committed capital."""

    def __init__(self, config: SimulationConfig):
        self.balance = config.initial_capital
        self.positions: dict[str, Position] = {}
        self.pending_orders: list[Order] = []
        self.filled_orders: list[Order] = []
        self.fee_rate = config.fee_rate           # default: 0.075% (Bybit taker)
        self.slippage_model = config.slippage      # "none" | "fixed" | "volume_based"

    @property
    def committed_capital(self) -> Decimal:
        """Капитал, залоченный в открытых позициях и pending ордерах."""
        in_positions = sum(
            abs(p.size * p.entry_price) for p in self.positions.values()
        )
        in_orders = sum(
            abs(o.qty * o.price) for o in self.pending_orders
        )
        return in_positions + in_orders

    @property
    def available_capital(self) -> Decimal:
        """Капитал, доступный для новых ордеров."""
        return max(Decimal(0), self.balance - self.committed_capital)

    def process_candle(self, candle: pd.Series) -> list[Fill]:
        """Проверяет исполнение pending orders по high/low свечи.
        Возвращает список fills для атрибуции."""
        fills = []
        for order in list(self.pending_orders):
            if order.side == "buy" and candle.low <= order.price:
                fill = self._fill(order, fill_price=order.price, candle=candle)
                fills.append(fill)
            elif order.side == "sell" and candle.high >= order.price:
                fill = self._fill(order, fill_price=order.price, candle=candle)
                fills.append(fill)
        return fills

    def _fill(self, order, fill_price, candle) -> Fill:
        """Исполнить ордер с учётом комиссии и проскальзывания."""
        slippage = self._calc_slippage(order, candle)
        actual_price = fill_price + slippage
        fee = abs(order.qty * actual_price) * self.fee_rate
        self.balance -= fee
        self.pending_orders.remove(order)
        self.filled_orders.append(order)
        # Обновить positions...
        return Fill(order=order, price=actual_price, fee=fee)

    def cancel_all_pending(self, symbol: str = None) -> list[Order]:
        """Отменить все pending ордера. Используется при transition и halt."""
        to_cancel = [
            o for o in self.pending_orders
            if symbol is None or o.symbol == symbol
        ]
        for order in to_cancel:
            self.pending_orders.remove(order)
        return to_cancel
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

    @staticmethod
    def transition_penalty(order, candle, base_bps: float = 3.0) -> float:
        """Повышенное проскальзывание при принудительном закрытии (transition/halt).
        Моделирует market impact спешного выхода."""
        return order.price * (base_bps / 10000)
```

---

## 5. Strategy Adapters — Адаптеры стратегий

### 5.0. Базовый интерфейс

Каждая стратегия имеет бэктест-адаптер, возвращающий `Signal` с `SignalType`:

```python
class BaseBacktestStrategy(ABC):
    """Единый интерфейс для всех стратегий в бэктесте."""

    @abstractmethod
    def evaluate(self, candle: pd.Series,
                 state: ExchangeState) -> Signal | list[Signal] | None:
        """Получить торговый сигнал(ы) на основе текущей свечи.
        Каждый Signal содержит signal_type для маршрутизации через SMC Filter."""

    @abstractmethod
    def get_parameter_space(self) -> dict[str, list]:
        """Вернуть пространство параметров для оптимизации."""

    @abstractmethod
    def from_params(self, params: dict) -> "BaseBacktestStrategy":
        """Создать экземпляр с указанными параметрами."""

    def on_transition_out(self, state: ExchangeState) -> list[Signal]:
        """Вызывается при переключении НА ДРУГУЮ стратегию.
        Возвращает exit-сигналы для закрытия позиций текущей стратегии.
        По умолчанию: force close all."""
        signals = []
        for pos in state.open_positions:
            signals.append(Signal(
                symbol=pos.symbol,
                side="sell" if pos.side == "long" else "buy",
                qty=abs(pos.size),
                price=None,  # market
                signal_type=SignalType.EXIT_TRANSITION,
                strategy_source=self.name,
            ))
        return signals
```

### 5.1. Grid Adapter

```python
class GridBacktestAdapter(BaseBacktestStrategy):
    """Адаптер Grid-стратегии для бэктестинга.
    Переиспользует существующий GridCalculator и GridOrderManager.

    Grid counter-orders помечаются как GRID_COUNTER → обходят SMC Filter.
    Это предотвращает 'сетку с дырками', когда SMC отклоняет
    отдельные уровни и ломает Grid-цикл.
    """
    name = "grid"

    params = {
        "num_levels": [8, 10, 12, 15, 20, 25, 30],
        "profit_per_grid": [0.001, 0.003, 0.005, 0.008, 0.01, 0.015],
        "grid_type": ["arithmetic", "geometric"],
        "range_factor": [1.0, 1.5, 2.0, 2.5],  # множитель ATR для диапазона
    }

    def evaluate(self, candle, state) -> list[Signal]:
        signals = []

        if not self._grid_initialized:
            # Первичная установка сетки → ENTRY (пройдёт SMC Grid-фильтр)
            signals.append(Signal(
                signal_type=SignalType.ENTRY,
                strategy_source="grid",
                metadata={"grid_center": candle.close, "grid_range": self._calc_range()},
                # ...
            ))
        else:
            # Проверить fills и создать counter-orders
            for fill in state.recent_fills:
                counter = self._create_counter_order(fill)
                counter.signal_type = SignalType.GRID_COUNTER  # обходит SMC!
                signals.append(counter)

            # Проверить SL для всей сетки
            if self._grid_sl_hit(candle):
                signals.append(Signal(
                    signal_type=SignalType.EXIT_SL,  # обходит SMC!
                    # ...
                ))

        return signals

    def on_transition_out(self, state) -> list[Signal]:
        """При переключении: отменить все Grid-ордера, закрыть net позицию."""
        # Pending ордера отменяются SimulatedExchange.cancel_all_pending()
        # Здесь закрываем net позицию если есть
        net = state.get_net_position(self._symbol)
        if net and abs(net.size) > 0:
            return [Signal(
                signal_type=SignalType.EXIT_TRANSITION,
                side="sell" if net.size > 0 else "buy",
                qty=abs(net.size),
                price=None,  # market
                strategy_source="grid",
            )]
        return []
```

### 5.2. DCA Adapter

```python
class DCABacktestAdapter(BaseBacktestStrategy):
    """Адаптер DCA-стратегии.

    Определение 'позиции' для DCA: 1 deal = base order + safety orders.
    Risk Aggregator разрешает max 1 deal на пару.
    """
    name = "dca"

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

    def evaluate(self, candle, state) -> Signal | None:
        # Рассчитать confluence score (EMA, ADX, RSI, BB, Volume)
        # Base order → signal_type = ENTRY (проходит SMC Filter)
        # Safety orders → signal_type = ENTRY (проходит SMC Filter)
        # Take-Profit → signal_type = EXIT_TP (обходит SMC!)
        # Trailing stop → signal_type = EXIT_SL (обходит SMC!)
        ...
```

### 5.3. Trend Follower Adapter

```python
class TrendFollowerBacktestAdapter(BaseBacktestStrategy):
    """Адаптер Trend Follower.

    Определение 'позиции': 1 направление на пару.
    Нельзя одновременно long и short.
    """
    name = "trend"

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

    def evaluate(self, candle, state) -> Signal | None:
        # EMA crossover → signal_type = ENTRY (проходит SMC)
        # ATR-based Stop-Loss → signal_type = EXIT_SL (обходит SMC!)
        # ATR-based Take-Profit → signal_type = EXIT_TP (обходит SMC!)
        # Trailing stop update → signal_type = EXIT_SL (обходит SMC!)
        ...
```

### 5.4. SMC Filter — Бэктест-версия с трекингом зон

> **Решённые конфликты:**
> - Grid фильтруется на уровне ВСЕЙ сетки, не отдельных ордеров (H3)
> - Зоны трекают касания и теряют confidence (M4)
> - Пересчёт зон раз в N свечей, а не на каждой итерации (L1)

```python
@dataclass
class SMCZone:
    """Зона SMC с трекингом здоровья."""
    price_low: float
    price_high: float
    zone_type: Literal["order_block", "fvg", "liquidity"]
    created_at: int              # индекс свечи
    touches: int = 0             # уникальные входы в зону (не per-candle!)
    max_touches: int = 2
    _was_inside: bool = False    # трекинг перехода снаружи → внутрь (NEW-H4)

    @property
    def is_alive(self) -> bool:
        return self.touches < self.max_touches

    @property
    def confidence_decay(self) -> float:
        """touch 0 → 1.0, touch 1 → 0.7, touch 2+ → dead (0.0)"""
        if not self.is_alive:
            return 0.0
        return max(0.0, 1.0 - self.touches * 0.3)


class SMCBacktestFilter:
    """SMC как фильтр для бэктестинга. Работает поверх любой стратегии.
    Различает Grid (фильтр всей сетки) и другие стратегии (фильтр отдельных сигналов)."""

    params = {
        "ob_lookback": [50, 100, 200],         # свечей для поиска Order Blocks
        "fvg_min_size_pct": [0.001, 0.003],    # минимальный размер FVG
        "min_confidence": [0.3, 0.4, 0.5],
        "enhanced_threshold": [0.6, 0.7, 0.8],
        "neutral_size_mult": [0.3, 0.5, 0.7],
    }

    def __init__(self, params: dict):
        self.zones: list[SMCZone] = []
        self.recalc_interval: int = 60  # каждые 60 свечей (эмуляция Master Loop 60 сек)
        self._params = params

    def recalculate_zones(self, data: pd.DataFrame, current_idx: int):
        """Пересчитать зоны. Вызывается раз в recalc_interval свечей."""
        self._prune_dead_zones()
        lookback = self._params.get("ob_lookback", 100)
        start = max(0, current_idx - lookback)
        window = data.iloc[start:current_idx]
        new_zones = self._find_order_blocks(window)
        new_zones += self._find_fvg(window)
        self._merge_zones(new_zones)

    def update_touches(self, current_price: float):
        """Обновить касания зон текущей ценой.

        Исправление конфликта NEW-H4: считаем уникальные ВХОДЫ в зону
        (переход снаружи → внутрь), а не каждую свечу внутри зоны.
        Иначе зона умирала бы за 2 последовательные свечи."""
        for zone in self.zones:
            is_inside = zone.price_low <= current_price <= zone.price_high
            if is_inside and not zone._was_inside:
                zone.touches += 1  # новый вход в зону
            zone._was_inside = is_inside

    def filter(self, signal: Signal, candle: pd.Series) -> Signal | None:
        """Маршрутизация фильтра по стратегии-источнику."""

        # Grid: фильтруем ВСЮ сетку целиком (не отдельные ордера)
        if signal.strategy_source == "grid" and "grid_range" in signal.metadata:
            return self._filter_grid(signal, candle)

        # DCA, Trend: фильтруем отдельный сигнал
        return self._filter_single(signal, candle)

    def _filter_grid(self, signal: Signal, candle: pd.Series) -> Signal | None:
        """Фильтрация Grid: оценка всей сетки как единого целого.
        Предотвращает 'сетку с дырками'."""
        grid_range = signal.metadata["grid_range"]
        grid_center = signal.metadata.get("grid_center", candle.close)

        zones_in_range = [
            z for z in self.zones
            if z.is_alive and self._overlaps(z, grid_range)
        ]

        # Проверить ликвидность, пересекающую > 30% сетки
        liquidity_zones = [z for z in zones_in_range if z.zone_type == "liquidity"]
        liquidity_coverage = self._calc_coverage(liquidity_zones, grid_range)
        if liquidity_coverage > 0.3:
            return None  # REJECT вся сетка

        # Оценить качество центра сетки
        support_zones = [z for z in zones_in_range if z.zone_type in ("order_block", "fvg")]
        if support_zones:
            best_zone = max(support_zones, key=lambda z: z.confidence_decay)
            confidence = best_zone.confidence_decay
        else:
            confidence = 0.5  # нет зон — нейтральный

        min_conf = self._params.get("min_confidence", 0.4)
        enhanced = self._params.get("enhanced_threshold", 0.7)

        if confidence >= enhanced:
            return signal  # ENHANCED — полный размер
        elif confidence >= min_conf:
            mult = Decimal(str(self._params.get("neutral_size_mult", 0.5)))
            # Исправление конфликта NEW-M3: проверяем жизнеспособность
            # уменьшенной Grid-сетки (per-level qty >= min_order_size)
            num_levels = signal.metadata.get("num_levels", 15)
            min_order = self._params.get("min_order_size", Decimal("0.001"))
            per_level = signal.qty * mult / num_levels
            if per_level < min_order:
                return None  # REJECT: сетка нежизнеспособна при уменьшенном размере
            signal.qty = signal.qty * mult
            return signal  # NEUTRAL — уменьшенный
        else:
            return None  # REJECT

    def _filter_single(self, signal: Signal, candle: pd.Series) -> Signal | None:
        """Фильтрация одиночного сигнала (DCA, Trend Follower).

        Исправление конфликта NEW-H3: добавлен _zone_quality() для
        консистентности с продакшен-формулой (Algorithm 5.4):
        confidence = decay × zone_quality (а не просто decay)."""
        nearest = self._find_nearest_alive_zone(signal.price or candle.close)
        if nearest is None:
            # Нет зон → нейтральный. Осознанное решение (NEW-L1):
            # отсутствие SMC-данных ≠ плохой сигнал.
            confidence = 0.5
        else:
            confidence = nearest.confidence_decay * self._zone_quality(nearest, signal)

        min_conf = self._params.get("min_confidence", 0.4)
        enhanced = self._params.get("enhanced_threshold", 0.7)

        if confidence >= enhanced:
            return signal
        elif confidence >= min_conf:
            mult = Decimal(str(self._params.get("neutral_size_mult", 0.5)))
            signal.qty = signal.qty * mult
            return signal
        else:
            return None

    def _prune_dead_zones(self):
        self.zones = [z for z in self.zones if z.is_alive]
```

---

## 6. Режимы бэктестинга

### 6.1. Single Strategy Backtest

Тестирует одну стратегию на одной паре:

```
Input:  BTC/USDT 1h, 2024-01-01 to 2025-12-31, Grid strategy
Output: ROI, Sharpe, Calmar, Max Drawdown, Win Rate, Trade Count
```

Использует `UniversalSimulator` с одним адаптером. SMC Filter опционален.

### 6.2. Multi-Strategy Backtest — Симуляция полного алгоритма v2.0

> **Ключевое нововведение.** Заменяет отдельный Hybrid-адаптер.
> Использует тот же RegimeClassifier и StrategyRouter что и продакшен,
> с полным гистерезисом и исправленным confirmation_counter.

```python
class MultiStrategyBacktest:
    """Симуляция полного алгоритма v2.0 на исторических данных.

    Решённые конфликты:
    - H7: confirmation_counter со сбросом при возврате к текущему режиму
    - M3: гистерезис встроен в RegimeClassifier (единый источник истины)
    - H9: таймаут на transition (2 часа в свечах)
    - M1: HYBRID удалён, Router переключает Grid/DCA напрямую
    """

    TRANSITION_TIMEOUT_HOURS = 2  # 2 часа — единица измерения одна для всех TF

    def __init__(self, config: MultiStrategyConfig):
        # Исправление конфликта NEW-C2: ранее TRANSITION_TIMEOUT_CANDLES = 120
        # был фиксированным, что давало 120 часов на 1h TF вместо 2 часов.
        # Теперь timeout вычисляется динамически:
        tf_minutes = config.timeframe_minutes  # 1h=60, 5m=5, 1d=1440
        self.transition_timeout_candles = (self.TRANSITION_TIMEOUT_HOURS * 60) // tf_minutes
        self.classifier = RegimeClassifier()  # тот же что в продакшене
        self.router = StrategyRouter()        # тот же что в продакшене
        self.smc_filter = SMCBacktestFilter(config.smc_params)
        self.exchange = SimulatedExchange(config)
        self.risk_manager = BacktestRiskManager(config)
        self.journal = MultiStrategyJournal()

        # Адаптеры стратегий
        self.adapters = {
            "grid": GridBacktestAdapter(config.grid_params),
            "dca": DCABacktestAdapter(config.dca_params),
            "trend": TrendFollowerBacktestAdapter(config.trend_params),
        }

    def run(self, data: pd.DataFrame, pair: str) -> BacktestResult:
        current_strategy = None
        current_regime = None

        for i, candle in data.iterrows():
            # 1. Исполнить pending orders
            self.exchange.process_candle(candle)

            # 2. Определить режим (с гистерезисом)
            snapshot = self._build_snapshot(candle, data, i)
            regime = self.classifier.classify(snapshot, current_regime)

            # 3. Определить целевую стратегию
            target = self.router.route(regime)

            # 4. Проверить переключение (с confirmation_counter)
            # Исправление конфликта NEW-M1: evaluate_transition при
            # current_regime=None немедленно возвращает True (cold start),
            # поэтому первая стратегия назначается без задержки.
            if self.router.evaluate_transition(regime, current_regime):
                if current_strategy is not None:
                    transition_cost = self._execute_transition(
                        current_strategy, target, candle
                    )
                    self.journal.record_transition(i, candle, regime, target, transition_cost)
                current_strategy = self.adapters[target]
                current_regime = regime

            # 5. Обновить SMC-зоны (раз в N свечей)
            if i % self.smc_filter.recalc_interval == 0:
                self.smc_filter.recalculate_zones(data, i)
            self.smc_filter.update_touches(candle.close)

            # 6. Выполнить стратегию
            if current_strategy:
                signals = current_strategy.evaluate(candle, self.exchange.state)
                for signal in self._ensure_list(signals):
                    if signal is None:
                        continue
                    # Маршрутизация через SMC (только ENTRY)
                    if signal.signal_type == SignalType.ENTRY:
                        signal = self.smc_filter.filter(signal, candle)
                    if signal and self.risk_manager.allow(signal, self.exchange.state):
                        self.exchange.execute(signal)

            # 7. Risk check (Emergency Halt симуляция)
            # Исправление конфликта NEW-H1: Emergency Halt прерывает
            # незавершённые transitions и принудительно освобождает locks.
            halt_event = self.risk_manager.check_portfolio_halt(self.exchange.state)
            if halt_event:
                # Если transition в процессе — прервать
                if self._transition_in_progress:
                    self._abort_transition(candle)
                    self.journal.record_transition_abort(i, candle, "emergency_halt")
                self._simulate_emergency_halt(halt_event, candle)
                self.journal.record_halt(i, candle, halt_event)

            # 8. Журнал
            self.journal.record(candle, self.exchange.state, current_regime)

        return self.journal.to_result()

    def _execute_transition(self, old_strategy, new_target, candle) -> TransitionCost:
        """Симуляция Graceful Transition с учётом стоимости переключения."""
        cost = TransitionCost()

        if old_strategy:
            # 1. Отменить pending ордера
            cancelled = self.exchange.cancel_all_pending()
            cost.cancelled_orders = len(cancelled)

            # 2. Получить exit-сигналы от старой стратегии
            exit_signals = old_strategy.on_transition_out(self.exchange.state)
            for signal in exit_signals:
                # Exit при transition → повышенное проскальзывание
                signal.metadata["slippage_model"] = "transition_penalty"
                self.exchange.execute(signal)
                cost.forced_closes += 1
                cost.transition_slippage += signal.metadata.get("actual_slippage", 0)

        return cost

    def _simulate_emergency_halt(self, halt_event, candle):
        """Симуляция Emergency Halt в бэктесте.

        В продакшене оператор выбирает действие. В бэктесте моделируем
        default поведение: отменить ордера + tight SL (1.5× ATR)."""
        self.exchange.cancel_all_pending()
        for pos in list(self.exchange.positions.values()):
            if abs(pos.size) > 0:
                atr = candle.get("atr_14", candle.close * 0.02)
                tight_sl = pos.entry_price - (1.5 * atr) if pos.side == "long" \
                    else pos.entry_price + (1.5 * atr)
                self.exchange.place_sl(pos.symbol, tight_sl)
```

**Что позволяет Multi-Strategy Backtest сравнить:**

```
1. "Всегда Grid" vs "Всегда DCA" vs "Всегда Trend" vs "Адаптивное v2.0"
2. Оптимальные пороги гистерезиса (ADX_ENTER_TRENDING, ADX_EXIT_TRENDING)
3. Оптимальный CONFIRMATION_COUNT (2, 3, 5)
4. Стоимость ложных переключений (transition_cost: slippage + forced closes)
5. Стоимость Emergency Halt событий
6. Влияние SMC Filter на общий P&L (с фильтром vs без)
```

### 6.3. Portfolio Backtest — Симуляция портфеля

> **Решённые конфликты:**
> - H5: Capital Allocator с нормализацией (сумма = 100% Active Pool)
> - H6: committed/available capital (overcommitted = no new orders)
> - H8: Dynamic Correlation Monitor + STRESS_MODE
> - C2: Emergency Halt с 3-stage протоколом
> - M2: Cold start performance_factor = 0.8

```python
class PortfolioBacktest:
    """Симуляция портфеля из нескольких пар.
    Моделирует Capital Allocator, Risk Aggregator, Dynamic Correlation."""

    def __init__(self, config: PortfolioConfig):
        self.total_capital = config.initial_capital
        self.reserve_pct = Decimal("0.15")
        self.allocator = BacktestCapitalAllocator(config)
        self.risk_agg = BacktestPortfolioRisk(config)
        self.correlation_monitor = BacktestCorrelationMonitor()

        # Per-pair simulators
        self.pair_sims: dict[str, MultiStrategyBacktest] = {}

    def run(self, pairs: list[str],
            data: dict[str, pd.DataFrame]) -> PortfolioResult:

        # Синхронизировать свечи по timestamp
        timeline = self._merge_timelines(data)

        # Инициализировать per-pair симуляторы
        for pair in pairs:
            self.pair_sims[pair] = MultiStrategyBacktest(self._pair_config(pair))

        pair_performance: dict[str, PairPerformance] = {}
        rebalance_counter = 0

        for ts_idx, timestamp in enumerate(timeline):

            # === РЕБАЛАНСИРОВКА (каждые 240 свечей ~ 4 часа на 1h) ===
            rebalance_counter += 1
            if rebalance_counter >= 240:
                rebalance_counter = 0

                # Dynamic Correlation Check
                returns_24h = self._calc_returns_24h(data, pairs, ts_idx)
                stress = self.correlation_monitor.check(pairs, returns_24h)
                if stress == StressLevel.HIGH:
                    self.risk_agg.enter_stress_mode()
                    # Суммарная экспозиция → 40% вместо 70%
                else:
                    self.risk_agg.exit_stress_mode()

                # Capital Allocation с нормализацией
                pair_regimes = {
                    p: self.pair_sims[p].current_regime for p in pairs
                }
                allocations = self.allocator.allocate(
                    pairs, pair_regimes, pair_performance,
                    stress_mode=self.risk_agg.stress_mode
                )
                for pair in pairs:
                    alloc = allocations[pair]
                    alloc.committed = self.pair_sims[pair].exchange.committed_capital
                    self.pair_sims[pair].set_allocation(alloc)

            # === PER-PAIR EXECUTION ===
            for pair in pairs:
                if pair not in data or timestamp not in data[pair].index:
                    continue

                candle = data[pair].loc[timestamp]
                sim = self.pair_sims[pair]

                # Check: overcommitted → skip new orders
                if sim.allocation and sim.allocation.overcommitted:
                    sim.allow_new_entries = False
                else:
                    sim.allow_new_entries = True

                # Portfolio-level risk check BEFORE execution
                # Исправление NEW-H2 + NEW-M4: используем RiskModeManager
                # с иерархией и мультипликативными модификаторами
                total_exposure = sum(
                    s.exchange.committed_capital for s in self.pair_sims.values()
                )
                max_exposure = self.risk_agg.get_max_exposure()  # 70% или 40% в STRESS
                if total_exposure > self.total_capital * max_exposure:
                    continue  # skip this pair

                # Исправление NEW-H5: Reserve enforcement
                # Если committed > 90% total → мягкое сокращение
                if total_exposure > self.total_capital * Decimal("0.90"):
                    self.risk_agg.flag_reserve_breach(pair, sim)

                # Apply size multiplier (REDUCED × STRESS = multiplicative)
                sim.size_multiplier = self.risk_agg.get_size_multiplier()

                # Execute one step
                sim.step(candle, data[pair], ts_idx)

                # Update performance
                pair_performance[pair] = sim.get_performance()

            # === PORTFOLIO METRICS ===
            portfolio_equity = sum(
                s.exchange.balance for s in self.pair_sims.values()
            )
            self.journal.record_portfolio(timestamp, portfolio_equity, allocations)

            # === EMERGENCY HALT CHECK ===
            daily_loss = self._calc_daily_loss(portfolio_equity)
            if daily_loss > 0.10:  # > 10%
                self._simulate_portfolio_halt()
                self.journal.record_halt(timestamp, daily_loss)

        return self.journal.to_portfolio_result()

    def _simulate_portfolio_halt(self):
        """Emergency Halt: отменить все ордера, tight SL на все позиции.
        Исправление NEW-H1: также прерывает незавершённые transitions."""
        for sim in self.pair_sims.values():
            if sim._transition_in_progress:
                sim._abort_transition()
            sim.exchange.cancel_all_pending()
            for pos in list(sim.exchange.positions.values()):
                if abs(pos.size) > 0:
                    sim.exchange.place_tight_sl(pos)
```

**BacktestRiskModeManager — иерархия режимов (NEW-H2 + NEW-M4):**

```python
class BacktestRiskModeManager:
    """Управление режимами риска в бэктесте.
    Порядок приоритета: HALT > REDUCED > STRESS > DRAWDOWN > NORMAL.
    REDUCED + STRESS = мультипликативно (0.5 × 0.5 = 0.25)."""

    def __init__(self):
        self.emergency_halt = False
        self.reduced_mode = False     # daily loss > 5%
        self.stress_mode = False      # correlation > 0.8
        self.drawdown_mode = False    # DD > 15% ATH

    def get_size_multiplier(self) -> float:
        if self.emergency_halt:
            return 0.0
        multiplier = 1.0
        if self.reduced_mode:
            multiplier *= 0.5
        if self.stress_mode:
            multiplier *= 0.5
        return multiplier  # min = 0.25

    def get_max_exposure(self) -> Decimal:
        if self.stress_mode:
            return Decimal("0.40")
        return Decimal("0.70")

    def flag_reserve_breach(self, pair: str, sim):
        """NEW-H5: Reserve < 10% → пометить пару для сокращения."""
        # Наименее приоритетная пара (min performance_factor)
        # будет сокращена при следующей ребалансировке
        sim.pending_reduction = True

    def update(self, daily_loss: float, drawdown: float):
        self.emergency_halt = daily_loss > 0.10
        self.reduced_mode = daily_loss > 0.05
        self.drawdown_mode = drawdown > 0.15
```

**BacktestCapitalAllocator с нормализацией:**

```python
class BacktestCapitalAllocator:
    """Capital Allocator для бэктеста.
    Тот же алгоритм что в продакшене, включая нормализацию."""

    def allocate(self, pairs, pair_regimes, pair_performance,
                 stress_mode=False,
                 pairs_pending_reduction: set = None) -> dict[str, PairAllocation]:
        """Исправление NEW-H5: reserve_pct = target с enforcement.
        Если committed > 90% total, pairs_pending_reduction содержит
        пары для мягкого сокращения (target снижается на 50%)."""
        active_pool = self.total_capital * (1 - self.reserve_pct)

        # Stress mode → снизить active_pool
        if stress_mode:
            active_pool *= Decimal("0.57")  # 40% / 70% ≈ 0.57 от нормальной экспозиции

        # Raw allocations
        raw = {}
        for pair in pairs:
            w = self._pair_weight(pair)
            c = self._regime_confidence(pair_regimes.get(pair))
            p = self._performance_factor(pair_performance.get(pair))
            raw[pair] = w * c * p

        # НОРМАЛИЗАЦИЯ: сумма не превышает active_pool
        raw_total = sum(raw.values())
        if raw_total > 1.0:
            norm_factor = 1.0 / raw_total
            raw = {pair: alloc * norm_factor for pair, alloc in raw.items()}

        # Apply per-pair cap (25%) + reserve enforcement (NEW-H5)
        allocations = {}
        for pair in pairs:
            target = Decimal(str(raw[pair])) * active_pool
            target = min(target, active_pool * Decimal("0.25"))
            # Reserve enforcement: мягкое сокращение при breach
            if pairs_pending_reduction and pair in pairs_pending_reduction:
                target *= Decimal("0.5")  # снижаем target на 50%
            allocations[pair] = PairAllocation(target=target)

        return allocations

    def _performance_factor(self, perf) -> float:
        """Cold start: factor = 0.8 при < 10 сделок (не 0.0 → не deadlock)."""
        if perf is None or perf.total_trades < 10:
            return 0.8
        if perf.win_rate > 0.60:
            return 1.2
        elif perf.win_rate > 0.40:
            return 1.0
        elif perf.win_rate > 0.25:
            return 0.6
        else:
            return 0.0  # отключение при >= 10 сделок и win_rate < 25%
```

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

### 7.2. Multi-Strategy Optimization — Новое

> Помимо оптимизации параметров стратегий, оптимизируем **метапараметры** v2.0:

```python
class MultiStrategyOptimizer:
    """Оптимизация метапараметров алгоритма переключения."""

    meta_params = {
        # Гистерезис RegimeClassifier
        "adx_enter_trending": [28, 30, 32, 35],
        "adx_exit_trending": [22, 25, 28],
        "adx_enter_ranging": [15, 18, 20],
        "adx_exit_ranging": [20, 22, 25],

        # Confirmation
        "confirmation_count": [2, 3, 5],
        "min_regime_duration_candles": [120, 240, 480],  # 2h, 4h, 8h (на 1h TF)

        # SMC Filter
        "smc_enabled": [True, False],
        "smc_min_confidence": [0.3, 0.4, 0.5],
        "smc_enhanced_threshold": [0.6, 0.7, 0.8],

        # Transition
        "transition_timeout_candles": [60, 120, 240],  # 1h, 2h, 4h
    }
```

### 7.3. Параллельная обработка

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

### 7.4. Objective Functions — Целевые функции

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

    # Комбинированная метрика для v2.0
    "composite": lambda r: (
        0.25 * normalize(r.total_return_pct)     # доходность
        + 0.25 * normalize(r.sharpe_ratio)        # стабильность
        + 0.15 * normalize(r.win_rate)            # точность
        + 0.20 * normalize(-r.max_drawdown_pct)   # защита капитала
        + 0.15 * normalize(-r.transition_cost_pct) # штраф за переключения
    ),
}
```

> **Новое в composite:** `transition_cost_pct` штрафует параметры, при которых
> стратегия переключается слишком часто (высокая стоимость переходов).

---

## 8. Reporting — Отчёты

### 8.1. BacktestResult — Стандартный результат

```python
@dataclass
class BacktestResult:
    # Идентификация
    strategy: str               # "grid" | "dca" | "trend" | "multi"
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

    # === НОВЫЕ ПОЛЯ для Multi-Strategy ===

    # Transition metrics
    total_transitions: int = 0
    transition_cost_total: Decimal = Decimal(0)
    transition_cost_pct: float = 0.0             # % от initial_capital
    forced_closes: int = 0                        # принудительные закрытия по таймауту
    avg_transition_duration: timedelta = timedelta(0)

    # Regime breakdown
    regime_distribution: dict[str, float] = None  # {"TIGHT_RANGE": 0.35, ...}
    strategy_distribution: dict[str, float] = None # {"grid": 0.40, "dca": 0.35, ...}

    # SMC Filter impact
    smc_entries_filtered: int = 0                 # сколько входов прошло SMC
    smc_entries_rejected: int = 0                 # сколько входов отклонено
    smc_entries_reduced: int = 0                  # сколько входов уменьшено (NEUTRAL)

    # Emergency Halt events
    halt_events: int = 0
    halt_total_duration: timedelta = timedelta(0)

    # Strategy-specific
    metadata: dict = None           # Grid: cycles, levels filled, etc.
                                    # DCA: safety orders used, avg accumulation
                                    # Trend: trends caught, false signals
```

### 8.2. PortfolioResult — Расширенный результат для портфеля

```python
@dataclass
class PortfolioResult(BacktestResult):
    """Результат портфельного бэктеста."""

    # Per-pair results
    pair_results: dict[str, BacktestResult] = None

    # Capital allocation history
    allocation_history: list[dict[str, PairAllocation]] = None

    # Correlation
    avg_pairwise_correlation: float = 0.0
    stress_mode_pct: float = 0.0      # % времени в STRESS_MODE
    max_correlated_exposure: float = 0.0

    # Diversification
    diversification_ratio: float = 0.0  # portfolio_return / sum(pair_returns)
    overcommitted_events: int = 0       # сколько раз пара была overcommitted
```

### 8.3. Визуализация (Plotly)

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
  │         -8.3% max DD            │
  └──────────────────────────────────┘

Chart 3: Monthly Returns Heatmap
  ┌────┬────┬────┬────┬────┬────┐
  │Jan │Feb │Mar │Apr │May │Jun │
  │+2.1│-0.5│+3.2│+1.8│+0.3│-1.1│
  └────┴────┴────┴────┴────┴────┘

Chart 4: Strategy Regime Timeline (Multi-Strategy)
  ┌──────────────────────────────────────────────┐
  │ GRID ████████░░ DCA ██████░░ TREND ██████████│
  │ (sideways)    (bear)       (bull)            │
  │                                              │
  │ ↕ transitions: 5 | cost: -0.8%              │
  │ ⚠ halt events: 1 | duration: 47h            │
  └──────────────────────────────────────────────┘

Chart 5: Capital Allocation Over Time (Portfolio)
  ┌──────────────────────────────────┐
  │▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░│ BTC 35%
  │████████████░░░░░░░░░░░░░░░░░░░░░│ ETH 28%
  │▒▒▒▒▒▒▒▒░░░░░░░░░░░░░░░░░░░░░░░░│ SOL 15%
  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│ Reserve 15%
  └──────────────────────────────────┘

Chart 6: Correlation Heatmap + Stress Periods (Portfolio)
  ┌──────────────────────────────────┐
  │  STRESS ████░░░░░████░░░░░░░░░░░│ 12% of time
  │  Corr: ≈0.4 avg, 0.92 peak     │
  └──────────────────────────────────┘
```

### 8.4. Сравнительный отчёт

```
┌──────────────────────────────────────────────────────────────────────┐
│              COMPARISON: BTC/USDT 2024-2025                           │
├──────────────────┬──────┬──────┬──────┬──────────────────────────────┤
│ Metric           │ Grid │ DCA  │Trend │ Multi-Strategy (v2.0)        │
├──────────────────┼──────┼──────┼──────┼──────────────────────────────┤
│ ROI              │+8.2% │+12.1%│+18.5%│ +22.7%                      │
│ Max Drawdown     │-4.1% │-8.7% │-11.2%│ -7.3%                       │
│ Sharpe           │ 1.82 │ 1.45 │ 1.21 │  2.14                       │
│ Win Rate         │ 78%  │ 65%  │ 52%  │  68%                        │
│ Trades           │ 342  │  47  │  31  │  198                        │
│ Profit Factor    │ 2.1  │ 1.8  │ 2.4  │  2.6                        │
│ Transitions      │  —   │  —   │  —   │  5 (cost: -0.8%)            │
│ Halt Events      │  —   │  —   │  —   │  1 (duration: 47h)          │
│ SMC Reject Rate  │  —   │  —   │  —   │  23% entries filtered       │
├──────────────────┴──────┴──────┴──────┴──────────────────────────────┤
│ Verdict: Multi-Strategy v2.0 achieves best risk-adjusted returns.    │
│ Transition cost (-0.8%) offset by better regime adaptation (+14.5%). │
│ SMC filter eliminated 23% of losing entries.                         │
│ Emergency Halt correctly triggered during -12% drawdown period.      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Интеграция с Web UI

### 9.1. API Endpoints

```
POST /api/v1/backtesting/run
  Body: {
    "mode": "single" | "multi_strategy" | "portfolio",
    "strategy": "grid" | "dca" | "trend",       // для mode=single
    "symbol": "BTC/USDT",                        // для single и multi_strategy
    "pairs": ["BTC/USDT", "ETH/USDT", ...],     // для portfolio
    "timeframe": "1h",
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
    "params": { ... },                  // опционально: если нет → оптимизация
    "smc_filter": true,                 // включить SMC Enhancement
    "slippage_model": "volume_based",   // реалистичность
    "optimize": {
      "enabled": true,
      "objective": "composite",
      "walk_forward": true,
      "include_meta_params": true       // оптимизировать гистерезис и transition
    }
  }

GET /api/v1/backtesting/status/{job_id}
  Response: { "status": "running", "progress": 45, "eta_seconds": 120 }

GET /api/v1/backtesting/result/{job_id}
  Response: BacktestResult (JSON) с transition_cost, halt_events, smc stats

GET /api/v1/backtesting/compare
  Query: job_ids=1,2,3
  Response: Сравнительная таблица (Grid vs DCA vs Trend vs Multi)

POST /api/v1/backtesting/export-preset/{job_id}
  Response: YAML preset для продакшен-деплоя
```

### 9.2. WebSocket прогресс

```
WS /ws/backtesting/{job_id}
  Сообщения:
    {"type": "progress", "pct": 45, "current_date": "2024-06-15"}
    {"type": "trade", "side": "buy", "price": 65000, "qty": 0.01, "signal_type": "entry"}
    {"type": "regime_change", "from": "TIGHT_RANGE", "to": "BEAR_TREND", "strategy": "dca"}
    {"type": "transition", "from": "grid", "to": "dca", "cost": -120.50, "forced": false}
    {"type": "smc_filter", "action": "reject", "signal_price": 95000, "confidence": 0.32}
    {"type": "halt", "trigger": "daily_loss_10pct", "action": "tight_sl"}
    {"type": "stress_mode", "enabled": true, "correlation": 0.91}
    {"type": "equity_update", "value": 102350.50}
    {"type": "complete", "result_id": "abc123"}
```

---

## 10. Полный Pipeline — Как запускать

### 10.1. Single Strategy Backtest

```bash
python -m bot.backtesting.run \
  --strategy grid \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --smc-filter \
  --optimize \
  --objective sharpe

# Результат: JSON + equity curve PNG + preset YAML
# SMC Filter активен для входов; exits обходят фильтр
```

### 10.2. Multi-Strategy Backtest

```bash
python -m bot.backtesting.run \
  --mode multi_strategy \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --smc-filter \
  --optimize-meta        # оптимизировать гистерезис + transition параметры

# Результат: equity curve + regime timeline + transition log + halt events
```

### 10.3. Multi-Strategy Comparison

```bash
python -m bot.backtesting.run \
  --mode compare \
  --symbol BTC/USDT \
  --timeframe 1h \
  --strategies grid,dca,trend,multi \
  --start 2024-01-01 \
  --end 2025-12-31

# Результат: таблица сравнения всех стратегий (включая transition_cost)
```

### 10.4. Portfolio Backtest

```bash
python -m bot.backtesting.run \
  --mode portfolio \
  --pairs BTC/USDT,ETH/USDT,SOL/USDT,DOGE/USDT,LINK/USDT \
  --timeframe 1h \
  --capital 100000 \
  --start 2024-01-01 \
  --end 2025-12-31

# Результат: портфельный equity curve, allocation history,
#   correlation report, stress_mode periods, halt events
```

### 10.5. Batch Optimization (45 pairs)

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
├── run.py                          # CLI entry point
├── batch.py                        # Batch processing 45 pairs
│
├── core/
│   ├── simulator.py                # UniversalSimulator с SignalType-маршрутизацией
│   ├── exchange.py                 # SimulatedExchange с committed/available capital
│   ├── slippage.py                 # SlippageModel + transition_penalty
│   ├── journal.py                  # TradeJournal
│   ├── result.py                   # BacktestResult + PortfolioResult
│   └── signal.py                   # Signal + SignalType enum
│
├── adapters/
│   ├── base.py                     # BaseBacktestStrategy (ABC) с on_transition_out()
│   ├── grid_adapter.py             # GridBacktestAdapter (GRID_COUNTER bypass)
│   ├── dca_adapter.py              # DCABacktestAdapter
│   ├── trend_adapter.py            # TrendFollowerBacktestAdapter
│   └── smc_filter.py               # SMCBacktestFilter с zone staleness
│
├── multi/
│   ├── multi_strategy.py           # MultiStrategyBacktest (transition, halt)
│   ├── portfolio.py                # PortfolioBacktest (allocation, correlation)
│   ├── # regime_classifier.py      # НЕ СОЗДАВАТЬ — импорт из bot.coordinator (NEW-M2)
│   ├── # strategy_router.py        # НЕ СОЗДАВАТЬ — импорт из bot.coordinator (NEW-M2)
│   ├── capital_allocator.py        # BacktestCapitalAllocator (обёртка над coordinator)
│   ├── risk_aggregator.py          # BacktestPortfolioRisk + BacktestRiskModeManager
│   ├── correlation_monitor.py      # BacktestCorrelationMonitor (STRESS_MODE)
│   └── transition.py               # TransitionCost, transition execution
│
├── optimization/
│   ├── optimizer.py                # ParallelOptimizer
│   ├── meta_optimizer.py           # MultiStrategyOptimizer (meta-params)
│   ├── walk_forward.py             # Walk-Forward Validation
│   └── objectives.py               # Objective functions + composite с transition_cost
│
├── data/
│   ├── loader.py                   # BacktestDataLoader
│   └── indicator_cache.py          # Precomputed indicators (.parquet)
│
├── reporting/
│   ├── charts.py                   # Plotly equity curves, heatmaps
│   ├── comparison.py               # Multi-strategy comparison table
│   ├── transition_report.py        # Transition log + cost analysis
│   ├── correlation_report.py       # Correlation heatmap + stress periods
│   └── preset_export.py            # YAML preset generation
│
└── api/
    ├── routes.py                   # FastAPI endpoints
    └── websocket.py                # Real-time progress updates
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
  │  Shared Code:│                    │  • StrategyRouter     │
  │  GridCalc    │◄─── same code ───→│  • GridCalculator     │
  │  DCAEngine   │                    │  • DCAEngine          │
  │  TrendLogic  │                    │  • TrendFollower      │
  │  SMCFilter   │                    │  • SMCFilter          │
  │  CapAlloc    │                    │  • CapitalAllocator   │
  │  RiskAgg     │                    │  • RiskAggregator     │
  └──────────────┘                    └──────────────────────┘

  Ключевой принцип: один и тот же код стратегий, классификатора,
  роутера, аллокатора и риск-агрегатора используется и в бэктесте,
  и в продакшене. Отличается только exchange layer.
```

Результат оптимизации — YAML preset — напрямую загружается в продакшен:

```yaml
# presets/BTCUSDT_optimized.yaml
symbol: BTC/USDT
strategy: multi_strategy
optimized_at: "2026-02-20"
walk_forward_validated: true
test_period: "2024-01-01 to 2025-12-31"

# Regime classification (с гистерезисом)
regime_thresholds:
  adx_enter_trending: 32
  adx_exit_trending: 25
  adx_enter_ranging: 18
  adx_exit_ranging: 22

# Strategy Router
router:
  confirmation_count: 3
  min_regime_duration_hours: 4
  transition_timeout_hours: 2

# Grid params
grid_params:
  num_levels: 15
  profit_per_grid: 0.005
  grid_type: arithmetic
  range_factor: 2.0

# DCA params
dca_params:
  safety_order_step: 0.03
  step_multiplier: 1.5
  volume_multiplier: 1.5
  take_profit_pct: 0.015
  max_safety_orders: 7

# Trend Follower params
trend_params:
  ema_fast: 20
  ema_slow: 50
  atr_sl_multiplier: 2.0
  atr_tp_multiplier: 2.5

# SMC Filter (только для ENTRY-сигналов)
smc_filter:
  enabled: true
  min_confidence: 0.4
  enhanced_threshold: 0.7
  neutral_size_mult: 0.5
  ob_lookback: 100
  zone_max_touches: 2

# Capital Allocator
capital:
  reserve_pct: 0.15
  max_per_pair_pct: 0.25
  max_per_strategy_pct: 0.40
  cold_start_factor: 0.8
  stress_mode_exposure_pct: 0.40

# Risk
risk:
  per_trade_max_loss_pct: 0.02
  per_pair_daily_loss_pct: 0.03
  portfolio_reduced_mode_pct: 0.05
  portfolio_halt_pct: 0.10
  drawdown_reduction_pct: 0.15
  cooldown_after_losses: 3
  cooldown_duration_hours: 2

# Correlation
correlation:
  stress_threshold: 0.8
  stress_pairs_ratio: 0.6

# Performance (Walk-Forward validated)
performance:
  roi: 22.7%
  sharpe: 2.14
  max_drawdown: -7.3%
  win_rate: 68%
  transitions: 5
  transition_cost: -0.8%
  halt_events: 1
  smc_reject_rate: 23%
```

---

## 13. Список решённых конфликтов в бэктестинге

| # | Конфликт в продакшене | Решение в бэктесте | Раздел |
|---|----------------------|---------------------|--------|
| C1 | SMC фильтрует Stop-Loss | `SignalType` маршрутизация: SMC только для `ENTRY` | 4.1 |
| C2 | Emergency Halt без протокола | `_simulate_emergency_halt()`: cancel + tight SL | 6.2, 6.3 |
| H3 | SMC дырявит Grid | `_filter_grid()`: оценка всей сетки; `GRID_COUNTER` обходит SMC | 5.1, 5.4 |
| H4 | "1 позиция" vs Grid/DCA | Per-strategy: 1 grid / 1 deal / 1 direction | 5.1, 5.2, 5.3 |
| H5 | Capital Allocator > 100% | `BacktestCapitalAllocator` с нормализацией | 6.3 |
| H6 | Ребалансировка vs залоченный капитал | `committed_capital` / `available_capital` / `overcommitted` | 4.2, 6.3 |
| H7 | confirmation_counter без сброса | `StrategyRouter.evaluate_transition()` с полным сбросом | 6.2 |
| H8 | Статические корреляции | `BacktestCorrelationMonitor` + STRESS_MODE | 6.3 |
| H9 | Transition Deadlock | `_execute_transition()` c `on_transition_out()` + force close | 6.2 |
| M1 | HYBRID двойной роутинг | HYBRID удалён; Multi-Strategy Backtest заменяет | 1, 6.2 |
| M2 | Cold start deadlock | `_performance_factor()`: 0.8 при < 10 сделок | 6.3 |
| M3 | Classifier vs Router рассинхрон | `RegimeClassifier` с встроенным гистерезисом | 6.2 |
| M4 | SMC-зоны не устаревают | `SMCZone.confidence_decay` + `touches` + pruning | 5.4 |
| L1 | SMC rate limit | `recalc_interval`: пересчёт зон раз в N свечей | 5.4 |
| NEW | Transition cost не учитывается | `TransitionCost`, `transition_penalty` slippage, `composite` objective | 4.3, 6.2, 7.4 |
| NEW | Halt events не моделируются | `_simulate_portfolio_halt()` в PortfolioBacktest | 6.3 |

### Дополнительные конфликты (Session 13 — выявлены и устранены)

| # | Конфликт | Решение в бэктесте | Раздел |
|---|----------|---------------------|--------|
| NEW-C1 | QUIET_TRANSITION: Grid+DCA на одной паре | Одна стратегия (Grid осторожный), без одновременной работы. Исправлено в Algorithm 4.1 | A:4.1 |
| NEW-C2 | TRANSITION_TIMEOUT_CANDLES=120 неверен для 1h+ | Динамический расчёт: `(TIMEOUT_HOURS × 60) / tf_minutes` | 6.2 |
| NEW-H1 | Emergency Halt во время transition → deadlock | `_abort_transition()` при halt; `_simulate_portfolio_halt()` прерывает transitions | 6.2, 6.3 |
| NEW-H2 | REDUCED MODE + STRESS MODE: 50%+50% = ? | `BacktestRiskModeManager`: мультипликативно (0.5×0.5=0.25), иерархия приоритетов | 6.3 |
| NEW-H3 | SMC `_filter_single()` без `_zone_quality()` | Добавлен `_zone_quality()` в `_filter_single()` для консистентности с продакшеном | 5.4 |
| NEW-H4 | SMC zone touches per-candle: зона умирает за 2 свечи | Per-entry подсчёт: `_was_inside` трекинг, инкремент только на переходе снаружи→внутрь | 5.4 |
| NEW-H5 | Reserve 15% не обеспечивается при overcommitted | `flag_reserve_breach()` + `pairs_pending_reduction` в allocator (target × 0.5) | 6.3 |
| NEW-M1 | 3 мин задержки первой стратегии при старте | `evaluate_transition(regime, None) → True` (cold start, немедленная инициализация) | 6.2 |
| NEW-M2 | Дублирование кода coordinator/ vs backtesting/multi/ | backtesting импортирует из coordinator/, не создаёт копии | 11 |
| NEW-M3 | Grid NEUTRAL = половинная сетка ниже min_order_size | Проверка `per_level >= min_order_size` в `_filter_grid()`, иначе REJECT | 5.4 |
| NEW-M4 | Drawdown + daily loss — двойной режим без приоритета | `BacktestRiskModeManager.update()`: иерархия HALT > REDUCED > STRESS > DRAWDOWN | 6.3 |
| NEW-L1 | SMC без зон → всегда NEUTRAL, не REJECT | Осознанное решение. Задокументировано: нет данных ≠ плохой сигнал | 5.4 |
| NEW-L2 | MarketRegime enum: код vs спецификация | Миграция enum описана в Algorithm 13. Backtesting использует v2.0 enum | A:13 |
