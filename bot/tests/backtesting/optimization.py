"""
Parameter Optimization Framework — Grid search over strategy parameters.

Evaluates each parameter combination by running a backtest and ranks
results by a chosen objective metric.

Usage:
    optimizer = ParameterOptimizer()
    result = await optimizer.optimize(
        strategy_factory=lambda params: MyStrategy(**params),
        param_grid={"take_profit_pct": [0.01, 0.02, 0.03], "stop_loss_pct": [0.01, 0.02]},
        data=data,
    )
"""

import itertools
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable

from bot.strategies.base import BaseStrategy
from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.multi_tf_data_loader import MultiTimeframeData
from bot.tests.backtesting.multi_tf_engine import (
    MultiTFBacktestConfig,
    MultiTimeframeBacktestEngine,
)


@dataclass
class OptimizationConfig:
    """Configuration for parameter optimization."""

    objective: str = "total_return_pct"
    higher_is_better: bool = True
    backtest_config: MultiTFBacktestConfig = field(
        default_factory=MultiTFBacktestConfig
    )


@dataclass
class OptimizationTrial:
    """Result of a single parameter combination trial."""

    params: dict[str, Any]
    result: BacktestResult
    objective_value: float


@dataclass
class OptimizationResult:
    """Results from parameter optimization."""

    best_params: dict[str, Any]
    best_result: BacktestResult
    best_objective: float
    all_trials: list[OptimizationTrial]
    objective_metric: str
    param_grid: dict[str, list[Any]]

    def top_n(self, n: int = 5) -> list[OptimizationTrial]:
        """Return top N trials by objective value."""
        return self.all_trials[:n]

    def get_param_impact(self, param_name: str) -> dict[Any, float]:
        """
        Average objective value for each value of a parameter.

        Useful for understanding parameter impact.
        """
        from collections import defaultdict

        groups: dict[Any, list[float]] = defaultdict(list)
        for trial in self.all_trials:
            val = trial.params.get(param_name)
            if val is not None:
                groups[val].append(trial.objective_value)

        return {k: sum(v) / len(v) for k, v in groups.items()}


class ParameterOptimizer:
    """
    Grid-search parameter optimizer for trading strategies.

    Takes a strategy factory callable and a parameter grid,
    evaluates each combination via backtesting, and returns ranked results.
    """

    def __init__(self, config: OptimizationConfig | None = None) -> None:
        self.config = config or OptimizationConfig()

    async def optimize(
        self,
        strategy_factory: Callable[[dict[str, Any]], BaseStrategy],
        param_grid: dict[str, list[Any]],
        data: MultiTimeframeData,
    ) -> OptimizationResult:
        """
        Run grid search optimization.

        Args:
            strategy_factory: Callable that takes a dict of parameters
                              and returns a BaseStrategy instance.
            param_grid: Dictionary mapping parameter names to lists of values.
            data: MultiTimeframeData to backtest on.

        Returns:
            OptimizationResult with ranked trials and best parameters.
        """
        combinations = self._generate_combinations(param_grid)
        trials: list[OptimizationTrial] = []

        for params in combinations:
            strategy = strategy_factory(params)
            engine = MultiTimeframeBacktestEngine(
                config=self.config.backtest_config
            )
            result = await engine.run(strategy, data)

            objective_val = self._get_objective_value(result)
            trials.append(OptimizationTrial(
                params=params,
                result=result,
                objective_value=objective_val,
            ))

        # Sort by objective
        trials.sort(
            key=lambda t: t.objective_value,
            reverse=self.config.higher_is_better,
        )

        best = trials[0] if trials else None

        return OptimizationResult(
            best_params=best.params if best else {},
            best_result=best.result if best else self._empty_result(),
            best_objective=best.objective_value if best else 0.0,
            all_trials=trials,
            objective_metric=self.config.objective,
            param_grid=param_grid,
        )

    def _generate_combinations(
        self, param_grid: dict[str, list[Any]]
    ) -> list[dict[str, Any]]:
        """Generate all parameter combinations from grid."""
        if not param_grid:
            return [{}]

        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        return combinations

    def _get_objective_value(self, result: BacktestResult) -> float:
        """Extract objective metric value from backtest result."""
        obj = self.config.objective

        value = getattr(result, obj, None)
        if value is None:
            return 0.0

        return float(value)

    def _empty_result(self) -> BacktestResult:
        """Create a minimal empty BacktestResult."""
        from datetime import datetime, timedelta

        now = datetime.now()
        return BacktestResult(
            strategy_name="none",
            symbol="",
            start_time=now,
            end_time=now,
            duration=timedelta(0),
            initial_balance=Decimal("0"),
            final_balance=Decimal("0"),
            total_return=Decimal("0"),
            total_return_pct=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            total_buy_orders=0,
            total_sell_orders=0,
            avg_profit_per_trade=Decimal("0"),
        )
