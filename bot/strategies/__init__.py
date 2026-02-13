"""
Trading Strategies Package
Contains implementation of various trading strategies.
"""

from bot.strategies.smc import SMCConfig, SMCStrategy
from bot.strategies.trend_follower import TrendFollowerConfig, TrendFollowerStrategy

__all__ = [
    "SMCStrategy",
    "SMCConfig",
    "TrendFollowerStrategy",
    "TrendFollowerConfig",
    "smc",
    "trend_follower",
]
