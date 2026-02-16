"""
Grid Backtesting data models — enums, configs, results.

Defines all data structures for grid-specific backtesting:
- Direction and cluster enums
- Backtest configuration
- Backtest results with grid-specific metrics
- Cluster presets for parameter ranges
- Optimization objectives
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from bot.strategies.grid.grid_calculator import GridSpacing


# =============================================================================
# Enums
# =============================================================================


class GridDirection(str, Enum):
    """Grid trading direction bias."""

    LONG = "long"  # Shift bounds down (expect upward movement)
    SHORT = "short"  # Shift bounds up (expect downward movement)
    NEUTRAL = "neutral"  # Symmetric around current price


class CoinCluster(str, Enum):
    """Coin volatility cluster classification."""

    BLUE_CHIPS = "blue_chips"  # BTC, ETH — low ATR%, high volume
    MID_CAPS = "mid_caps"  # SOL, AVAX — moderate volatility
    MEMES = "memes"  # DOGE, SHIB — high ATR%, low volume
    STABLE = "stable"  # Stablecoins — very low ATR%


class OptimizationObjective(str, Enum):
    """Objective function for parameter optimization."""

    ROI = "roi"
    SHARPE = "sharpe"
    CALMAR = "calmar"
    PROFIT_FACTOR = "profit_factor"


# =============================================================================
# Cluster Presets
# =============================================================================


@dataclass
class ClusterPreset:
    """Parameter ranges for a coin cluster — used by optimizer."""

    cluster: CoinCluster
    spacing_options: list[GridSpacing] = field(default_factory=lambda: [GridSpacing.ARITHMETIC])
    levels_range: tuple[int, int] = (10, 20)
    profit_per_grid_range: tuple[float, float] = (0.003, 0.008)
    amount_per_grid_range: tuple[float, float] = (50.0, 200.0)
    atr_multiplier_range: tuple[float, float] = (2.0, 4.0)


# Default presets per cluster
CLUSTER_PRESETS: dict[CoinCluster, ClusterPreset] = {
    CoinCluster.BLUE_CHIPS: ClusterPreset(
        cluster=CoinCluster.BLUE_CHIPS,
        spacing_options=[GridSpacing.ARITHMETIC, GridSpacing.GEOMETRIC],
        levels_range=(10, 20),
        profit_per_grid_range=(0.003, 0.008),
        amount_per_grid_range=(100.0, 500.0),
        atr_multiplier_range=(2.0, 4.0),
    ),
    CoinCluster.MID_CAPS: ClusterPreset(
        cluster=CoinCluster.MID_CAPS,
        spacing_options=[GridSpacing.ARITHMETIC, GridSpacing.GEOMETRIC],
        levels_range=(8, 15),
        profit_per_grid_range=(0.005, 0.015),
        amount_per_grid_range=(50.0, 300.0),
        atr_multiplier_range=(2.5, 5.0),
    ),
    CoinCluster.MEMES: ClusterPreset(
        cluster=CoinCluster.MEMES,
        spacing_options=[GridSpacing.GEOMETRIC],
        levels_range=(5, 10),
        profit_per_grid_range=(0.01, 0.03),
        amount_per_grid_range=(20.0, 100.0),
        atr_multiplier_range=(3.0, 6.0),
    ),
    CoinCluster.STABLE: ClusterPreset(
        cluster=CoinCluster.STABLE,
        spacing_options=[GridSpacing.ARITHMETIC],
        levels_range=(20, 30),
        profit_per_grid_range=(0.001, 0.003),
        amount_per_grid_range=(200.0, 1000.0),
        atr_multiplier_range=(1.0, 2.0),
    ),
}


# =============================================================================
# Backtest Configuration
# =============================================================================


@dataclass
class GridBacktestConfig:
    """Configuration for a single grid backtest run."""

    symbol: str = "BTCUSDT"
    timeframe: str = "1h"

    # Grid parameters
    upper_price: Decimal = Decimal("0")  # 0 = auto from ATR
    lower_price: Decimal = Decimal("0")  # 0 = auto from ATR
    num_levels: int = 15
    spacing: GridSpacing = GridSpacing.ARITHMETIC
    profit_per_grid: Decimal = Decimal("0.005")  # 0.5%
    amount_per_grid: Decimal = Decimal("100")  # quote currency per level

    # Direction
    direction: GridDirection = GridDirection.NEUTRAL

    # ATR auto-bounds
    atr_period: int = 14
    atr_multiplier: Decimal = Decimal("3.0")

    # Fees
    maker_fee: Decimal = Decimal("0.001")  # 0.1%
    taker_fee: Decimal = Decimal("0.001")  # 0.1%

    # Initial balance
    initial_balance: Decimal = Decimal("10000")  # quote currency

    # Risk
    stop_loss_pct: Decimal = Decimal("0.05")  # 5% grid-wide stop
    max_drawdown_pct: Decimal = Decimal("0.10")  # 10% max drawdown

    @property
    def auto_bounds(self) -> bool:
        """Whether to calculate bounds from ATR."""
        return self.upper_price == 0 or self.lower_price == 0


# =============================================================================
# Trade Record
# =============================================================================


@dataclass
class GridTradeRecord:
    """Single trade in the backtest."""

    timestamp: str
    side: str  # "buy" or "sell"
    price: float
    amount: float
    fee: float
    order_id: str
    grid_level: int = 0


# =============================================================================
# Equity Point
# =============================================================================


@dataclass
class EquityPoint:
    """Single point in the equity curve."""

    timestamp: str
    equity: float
    price: float
    unrealized_pnl: float = 0.0


# =============================================================================
# Backtest Result
# =============================================================================


@dataclass
class GridBacktestResult:
    """Result of a grid backtest with grid-specific metrics."""

    # Config used
    config: GridBacktestConfig = field(default_factory=GridBacktestConfig)

    # Basic metrics
    total_return_pct: float = 0.0
    total_pnl: float = 0.0
    final_equity: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0

    # Grid-specific metrics
    completed_cycles: int = 0
    grid_fill_rate: float = 0.0  # % of grid levels that were filled at least once
    avg_profit_per_cycle: float = 0.0
    price_left_grid_count: int = 0  # times price exited grid bounds
    max_one_sided_exposure: float = 0.0  # max quote in one direction
    total_fees_paid: float = 0.0

    # Risk-adjusted metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0

    # Time series
    equity_curve: list[EquityPoint] = field(default_factory=list)
    trade_history: list[GridTradeRecord] = field(default_factory=list)

    # Simulation metadata
    candles_processed: int = 0
    stopped_by_risk: bool = False
    stop_reason: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (without heavy time series)."""
        return {
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "total_return_pct": round(self.total_return_pct, 4),
            "total_pnl": round(self.total_pnl, 2),
            "final_equity": round(self.final_equity, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "completed_cycles": self.completed_cycles,
            "grid_fill_rate": round(self.grid_fill_rate, 4),
            "avg_profit_per_cycle": round(self.avg_profit_per_cycle, 4),
            "price_left_grid_count": self.price_left_grid_count,
            "max_one_sided_exposure": round(self.max_one_sided_exposure, 2),
            "total_fees_paid": round(self.total_fees_paid, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "profit_factor": round(self.profit_factor, 4),
            "candles_processed": self.candles_processed,
            "stopped_by_risk": self.stopped_by_risk,
            "stop_reason": self.stop_reason,
            "duration_seconds": round(self.duration_seconds, 2),
        }


# =============================================================================
# Coin Profile (used by clusterizer)
# =============================================================================


@dataclass
class CoinProfile:
    """Profile of a coin's volatility characteristics."""

    symbol: str
    cluster: CoinCluster
    atr_pct: float  # ATR as % of price
    avg_daily_volume: float
    max_gap_pct: float  # max single-candle gap
    volatility_score: float  # composite score 0-100
