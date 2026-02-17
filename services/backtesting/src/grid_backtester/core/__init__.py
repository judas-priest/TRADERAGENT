"""Core grid strategy components — calculator, order manager, risk manager, config."""

from grid_backtester.core.calculator import (
    GridCalculator,
    GridConfig,
    GridLevel,
    GridSpacing,
)
from grid_backtester.core.order_manager import (
    GridCycle,
    GridOrderManager,
    GridOrderState,
    OrderStatus,
)
from grid_backtester.core.risk_manager import (
    GridRiskAction,
    GridRiskConfig,
    GridRiskManager,
    RiskCheckResult,
    TrendState,
)
from grid_backtester.core.config import (
    GridStrategyConfig,
    VolatilityMode,
    VOLATILITY_PRESETS,
)

import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parents[5])
if _root not in sys.path:
    sys.path.insert(0, _root)

from bot.strategies.grid.exchange_protocol import IGridExchange  # noqa: F401,E402

__all__ = [
    "GridCalculator",
    "GridConfig",
    "GridLevel",
    "GridSpacing",
    "GridOrderManager",
    "GridOrderState",
    "GridCycle",
    "OrderStatus",
    "GridRiskManager",
    "GridRiskConfig",
    "GridRiskAction",
    "RiskCheckResult",
    "TrendState",
    "GridStrategyConfig",
    "VolatilityMode",
    "VOLATILITY_PRESETS",
    "IGridExchange",
]
