"""DCA Strategy Package — v2.0 Signal Generator, Position Manager, Risk Manager, Trailing Stop, Engine, Config, Backtester."""

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
from bot.strategies.dca.dca_engine import (
    DCAEngine,
    DealExitSignal,
    EngineAction,
    FalseSignalFilter,
)
from bot.strategies.dca.dca_config import (
    DCAStrategyConfig,
    MarketPreset,
    MARKET_PRESETS,
)
from bot.strategies.dca.dca_backtester import (
    BacktestResult,
    BacktestTrade,
    DCABacktester,
    compare_strategies,
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
    "DCAEngine",
    "EngineAction",
    "DealExitSignal",
    "FalseSignalFilter",
    "DCAStrategyConfig",
    "MarketPreset",
    "MARKET_PRESETS",
    "DCABacktester",
    "BacktestResult",
    "BacktestTrade",
    "compare_strategies",
]
