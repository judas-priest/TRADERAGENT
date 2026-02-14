"""DCA Strategy Package — v2.0 Signal Generator, Position Manager, and related utilities."""

from bot.strategies.dca.dca_signal_generator import (
    ConditionResult,
    DCASignalConfig,
    DCASignalGenerator,
    MarketState,
    SignalResult,
)
from bot.strategies.dca.dca_position_manager import (
    CloseResult,
    DCADeal,
    DCAOrder,
    DCAOrderConfig,
    DCAOrderStatus,
    DCAOrderType,
    DCAPositionManager,
    DealStatus,
    SafetyOrderLevel,
)

__all__ = [
    "DCASignalGenerator",
    "DCASignalConfig",
    "MarketState",
    "SignalResult",
    "ConditionResult",
    "DCAPositionManager",
    "DCAOrderConfig",
    "DCADeal",
    "DCAOrder",
    "DealStatus",
    "DCAOrderType",
    "DCAOrderStatus",
    "SafetyOrderLevel",
    "CloseResult",
]
