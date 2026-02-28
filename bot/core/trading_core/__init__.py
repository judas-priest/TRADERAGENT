"""Unified TradingCore — shared kernel for live bot and backtesting."""

from bot.core.trading_core.config import TradingCoreConfig
from bot.core.trading_core.core import TradingCore
from bot.core.trading_core.hybrid_coordinator import CoordinatedDecision, HybridCoordinator

__all__ = [
    "TradingCoreConfig",
    "TradingCore",
    "HybridCoordinator",
    "CoordinatedDecision",
]
