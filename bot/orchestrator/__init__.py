"""Bot orchestration module for coordinating trading strategies and lifecycle management."""

from bot.orchestrator.bot_orchestrator import BotOrchestrator, BotState
from bot.orchestrator.events import EventType, TradingEvent
from bot.orchestrator.health_monitor import (
    HealthMonitor,
    HealthCheckResult,
    HealthStatus,
    HealthThresholds,
)
from bot.orchestrator.market_regime import (
    MarketRegime,
    MarketRegimeDetector,
    RecommendedStrategy,
    RegimeAnalysis,
)
from bot.orchestrator.strategy_registry import (
    StrategyInstance,
    StrategyMetrics,
    StrategyRegistry,
    StrategyState,
)
from bot.orchestrator.strategy_selector import (
    SelectionResult,
    StrategySelector,
    StrategyWeight,
    TransitionRecord,
    TransitionState,
)

__all__ = [
    "BotOrchestrator",
    "BotState",
    "EventType",
    "TradingEvent",
    # v2.0
    "StrategyRegistry",
    "StrategyInstance",
    "StrategyState",
    "StrategyMetrics",
    "MarketRegimeDetector",
    "MarketRegime",
    "RecommendedStrategy",
    "RegimeAnalysis",
    "HealthMonitor",
    "HealthCheckResult",
    "HealthStatus",
    "HealthThresholds",
    "StrategySelector",
    "SelectionResult",
    "StrategyWeight",
    "TransitionRecord",
    "TransitionState",
]
