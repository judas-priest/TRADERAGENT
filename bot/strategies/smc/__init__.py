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

from bot.strategies.smc.smc_strategy import SMCStrategy
from bot.strategies.smc.config import SMCConfig, DEFAULT_SMC_CONFIG
from bot.strategies.smc.market_structure import (
    MarketStructureAnalyzer,
    TrendDirection,
    StructureBreak,
    SwingPoint,
    StructureEvent,
)
from bot.strategies.smc.confluence_zones import (
    ConfluenceZoneAnalyzer,
    OrderBlock,
    FairValueGap,
    ZoneType,
    ZoneStatus,
)
from bot.strategies.smc.entry_signals import (
    EntrySignalGenerator,
    SMCSignal,
    PriceActionPattern,
    PatternType,
    SignalDirection,
)
from bot.strategies.smc.position_manager import (
    PositionManager,
    PositionMetrics,
    PositionStatus,
    PerformanceStats,
)

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
