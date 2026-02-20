"""
Smart Money Concepts (SMC) Strategy Implementation

Complete SMC trading strategy with:
- Market Structure Analysis
- Confluence Zones (Order Blocks & Fair Value Gaps)
- Entry Signal Generation
- Position Management with Kelly Criterion

Author: TRADERAGENT Team
Version: 1.0.0
Issue: https://github.com/alekseymavai/TRADERAGENT/issues/123
"""

from bot.strategies.smc.config import DEFAULT_SMC_CONFIG, SMCConfig
from bot.strategies.smc.confluence_zones import (
    ConfluenceZoneAnalyzer,
    FairValueGap,
    LiquidityZone,
    OrderBlock,
    ZoneStatus,
    ZoneType,
)
from bot.strategies.smc.entry_signals import (
    EntrySignalGenerator,
    PatternType,
    PriceActionPattern,
    SignalDirection,
    SMCSignal,
)
from bot.strategies.smc.market_structure import (
    MarketStructureAnalyzer,
    StructureBreak,
    StructureEvent,
    SwingPoint,
    TrendDirection,
)
from bot.strategies.smc.position_manager import (
    PerformanceStats,
    PositionManager,
    PositionMetrics,
    PositionStatus,
)
from bot.strategies.smc.smc_strategy import SMCStrategy

__all__ = [
    # Main strategy
    "SMCStrategy",
    "SMCConfig",
    "DEFAULT_SMC_CONFIG",
    # Market Structure
    "MarketStructureAnalyzer",
    "TrendDirection",
    "StructureBreak",
    "SwingPoint",
    "StructureEvent",
    # Confluence Zones
    "ConfluenceZoneAnalyzer",
    "OrderBlock",
    "FairValueGap",
    "LiquidityZone",
    "ZoneType",
    "ZoneStatus",
    # Entry Signals
    "EntrySignalGenerator",
    "SMCSignal",
    "PriceActionPattern",
    "PatternType",
    "SignalDirection",
    # Position Management
    "PositionManager",
    "PositionMetrics",
    "PositionStatus",
    "PerformanceStats",
]

__version__ = "1.0.0"
