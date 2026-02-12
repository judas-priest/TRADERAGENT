"""
Trend-Follower Strategy Package
Adaptive trend-following strategy with market phase detection
"""

from bot.strategies.trend_follower.config import DEFAULT_TREND_FOLLOWER_CONFIG, TrendFollowerConfig
from bot.strategies.trend_follower.trend_follower_strategy import TrendFollowerStrategy

__all__ = [
    'TrendFollowerStrategy',
    'TrendFollowerConfig',
    'DEFAULT_TREND_FOLLOWER_CONFIG',
]
