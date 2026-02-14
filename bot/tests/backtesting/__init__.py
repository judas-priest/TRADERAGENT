"""Backtesting and market simulation framework"""

from .backtesting_engine import BacktestingEngine
from .market_simulator import MarketSimulator
from .monte_carlo import MonteCarloConfig, MonteCarloResult, MonteCarloSimulation
from .multi_tf_data_loader import MultiTimeframeData, MultiTimeframeDataLoader
from .multi_tf_engine import MultiTFBacktestConfig, MultiTimeframeBacktestEngine
from .optimization import OptimizationConfig, OptimizationResult, ParameterOptimizer
from .sensitivity import SensitivityAnalysis, SensitivityConfig, SensitivityResult
from .strategy_comparison import StrategyComparison, StrategyComparisonResult
from .test_data import HistoricalDataProvider
from .walk_forward import WalkForwardAnalysis, WalkForwardConfig, WalkForwardResult

__all__ = [
    "MarketSimulator",
    "BacktestingEngine",
    "HistoricalDataProvider",
    "MultiTimeframeDataLoader",
    "MultiTimeframeData",
    "MultiTimeframeBacktestEngine",
    "MultiTFBacktestConfig",
    "StrategyComparison",
    "StrategyComparisonResult",
    "WalkForwardAnalysis",
    "WalkForwardConfig",
    "WalkForwardResult",
    "MonteCarloSimulation",
    "MonteCarloConfig",
    "MonteCarloResult",
    "ParameterOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "SensitivityAnalysis",
    "SensitivityConfig",
    "SensitivityResult",
]
