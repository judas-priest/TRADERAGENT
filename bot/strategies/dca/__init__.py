"""DCA Strategy Package — v2.0 Signal Generator, Position Manager, Risk Manager, Trailing Stop."""

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
from bot.strategies.dca.dca_trailing_stop import (
    DCATrailingStop,
    TrailingStopConfig,
    TrailingStopResult,
    TrailingStopSnapshot,
    TrailingStopState,
    TrailingStopType,
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
    "DCATrailingStop",
    "TrailingStopConfig",
    "TrailingStopResult",
    "TrailingStopSnapshot",
    "TrailingStopState",
    "TrailingStopType",
]
