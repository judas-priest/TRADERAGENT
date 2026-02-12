"""
Trading Strategies Package
Contains implementation of various trading strategies.
"""

from bot.strategies.smc import SMCStrategy, SMCConfig
from bot.strategies.trend_follower import TrendFollowerStrategy, TrendFollowerConfig

__all__ = [
    'SMCStrategy',
    'SMCConfig',
    'TrendFollowerStrategy',
    'TrendFollowerConfig',
    'smc',
    'trend_follower'
]
