"""DCA Strategy Package — v2.0 Signal Generator, Position Manager, Risk Manager."""

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
from bot.strategies.dca.dca_risk_manager import (
    DCARiskAction,
    DCARiskConfig,
    DCARiskManager,
    DealRiskState,
    PortfolioRiskState,
    RiskCheckResult,
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
    "DCARiskManager",
    "DCARiskConfig",
    "DCARiskAction",
    "RiskCheckResult",
    "DealRiskState",
    "PortfolioRiskState",
]
