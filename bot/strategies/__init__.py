"""
Trading Strategies Package
Contains implementation of various trading strategies.

v2.0: Unified BaseStrategy interface with adapter pattern.
"""

from bot.strategies.base import (
    BaseMarketAnalysis,
    BaseSignal,
    BaseStrategy,
    ExitReason,
    PositionInfo,
    SignalDirection,
    StrategyPerformance,
)
from bot.strategies.dca import (
    ConditionResult,
    DCASignalConfig,
    DCASignalGenerator,
    MarketState,
    SignalResult,
)
from bot.strategies.grid import (
    GridCalculator,
    GridConfig,
    GridCycle,
    GridLevel,
    GridOrderManager,
    GridOrderState,
    GridSpacing,
    OrderStatus,
)
from bot.strategies.smc import SMCConfig, SMCStrategy
from bot.strategies.smc_adapter import SMCStrategyAdapter
from bot.strategies.trend_follower import TrendFollowerConfig, TrendFollowerStrategy
from bot.strategies.trend_follower_adapter import TrendFollowerAdapter

__all__ = [
    # Base types
    "BaseStrategy",
    "BaseSignal",
    "BaseMarketAnalysis",
    "SignalDirection",
    "ExitReason",
    "PositionInfo",
    "StrategyPerformance",
    # SMC
    "SMCStrategy",
    "SMCConfig",
    "SMCStrategyAdapter",
    # Trend Follower
    "TrendFollowerStrategy",
    "TrendFollowerConfig",
    "TrendFollowerAdapter",
    # Grid
    "GridCalculator",
    "GridConfig",
    "GridLevel",
    "GridSpacing",
    "GridOrderManager",
    "GridOrderState",
    "GridCycle",
    "OrderStatus",
    # DCA
    "DCASignalGenerator",
    "DCASignalConfig",
    "MarketState",
    "SignalResult",
    "ConditionResult",
    # Subpackages
    "smc",
    "trend_follower",
    "grid",
    "dca",
]
