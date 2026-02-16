"""Grid backtesting system — specialized for grid trading strategies."""

from bot.backtesting.grid.models import (
    CoinCluster,
    CoinProfile,
    ClusterPreset,
    CLUSTER_PRESETS,
    EquityPoint,
    GridBacktestConfig,
    GridBacktestResult,
    GridDirection,
    GridTradeRecord,
    OptimizationObjective,
)
from bot.backtesting.grid.simulator import GridBacktestSimulator
from bot.backtesting.grid.clusterizer import CoinClusterizer
from bot.backtesting.grid.optimizer import GridOptimizer, GridOptimizationResult, OptimizationTrial
from bot.backtesting.grid.reporter import GridBacktestReporter
from bot.backtesting.grid.system import GridBacktestSystem

__all__ = [
    # Models
    "CoinCluster",
    "CoinProfile",
    "ClusterPreset",
    "CLUSTER_PRESETS",
    "EquityPoint",
    "GridBacktestConfig",
    "GridBacktestResult",
    "GridDirection",
    "GridTradeRecord",
    "OptimizationObjective",
    # Core
    "GridBacktestSimulator",
    "CoinClusterizer",
    "GridOptimizer",
    "GridOptimizationResult",
    "OptimizationTrial",
    "GridBacktestReporter",
    "GridBacktestSystem",
]
