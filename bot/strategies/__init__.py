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
    # Subpackages
    "smc",
    "trend_follower",
]
