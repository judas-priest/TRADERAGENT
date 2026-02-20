"""
Sensitivity Analysis — Measure how individual parameters affect performance.

Varies one parameter at a time while holding others at baseline,
producing impact curves for each parameter.

Usage:
    sa = SensitivityAnalysis()
    result = await sa.run(
        strategy_factory=lambda p: MyStrategy(**p),
        base_params={"tp": 0.02, "sl": 0.01},
        param_ranges={"tp": [0.01, 0.02, 0.03, 0.04]},
        data=data,
    )
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bot.strategies.base import BaseStrategy
from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.multi_tf_data_loader import MultiTimeframeData
from bot.tests.backtesting.multi_tf_engine import (
    MultiTFBacktestConfig,
    MultiTimeframeBacktestEngine,
)


@dataclass
class SensitivityConfig:
    """Configuration for sensitivity analysis."""

    metrics: list[str] = field(
        default_factory=lambda: [
            "total_return_pct",
            "max_drawdown_pct",
            "win_rate",
            "sharpe_ratio",
        ]
    )
    backtest_config: MultiTFBacktestConfig = field(default_factory=MultiTFBacktestConfig)


@dataclass
class ParameterSensitivity:
    """Sensitivity results for a single parameter."""

    param_name: str
    values: list[Any]
    metrics: dict[str, list[float]]  # metric_name -> [value per param value]

    def get_range(self, metric: str) -> float:
        """Get the range (max - min) for a metric across parameter values."""
        vals = self.metrics.get(metric, [])
        if not vals:
            return 0.0
        return max(vals) - min(vals)

    def get_best_value(self, metric: str, higher_is_better: bool = True) -> Any:
        """Get parameter value that produces best metric result."""
        vals = self.metrics.get(metric, [])
        if not vals:
            return None
        idx = vals.index(max(vals) if higher_is_better else min(vals))
        return self.values[idx] if idx < len(self.values) else None


@dataclass
class SensitivityResult:
    """Complete sensitivity analysis results."""

    parameters: dict[str, ParameterSensitivity]
    baseline_result: BacktestResult
    base_params: dict[str, Any]

    def rank_by_impact(self, metric: str = "total_return_pct") -> list[tuple[str, float]]:
        """
        Rank parameters by their impact on a metric.

        Returns list of (param_name, range) sorted by impact (highest first).
        """
        impacts = []
        for name, sensitivity in self.parameters.items():
            impact = sensitivity.get_range(metric)
            impacts.append((name, impact))
        impacts.sort(key=lambda x: x[1], reverse=True)
        return impacts

    def most_sensitive_param(self, metric: str = "total_return_pct") -> str | None:
        """Return name of the parameter with the highest impact on metric."""
        ranking = self.rank_by_impact(metric)
        return ranking[0][0] if ranking else None


class SensitivityAnalysis:
    """
    One-at-a-time sensitivity analysis for strategy parameters.

    Varies each parameter individually while holding all others at baseline,
    then runs a backtest for each value and records metrics.
    """

    def __init__(self, config: SensitivityConfig | None = None) -> None:
        self.config = config or SensitivityConfig()

    async def run(
        self,
        strategy_factory: Callable[[dict[str, Any]], BaseStrategy],
        base_params: dict[str, Any],
        param_ranges: dict[str, list[Any]],
        data: MultiTimeframeData,
    ) -> SensitivityResult:
        """
        Run sensitivity analysis.

        Args:
            strategy_factory: Callable(params) -> BaseStrategy.
            base_params: Baseline parameter values.
            param_ranges: For each param, list of values to test.
            data: MultiTimeframeData for backtesting.

        Returns:
            SensitivityResult with per-parameter impact curves.
        """
        # Run baseline
        baseline_strategy = strategy_factory(base_params)
        engine = MultiTimeframeBacktestEngine(config=self.config.backtest_config)
        baseline_result = await engine.run(baseline_strategy, data)

        # Analyze each parameter
        parameters: dict[str, ParameterSensitivity] = {}

        for param_name, values in param_ranges.items():
            sensitivity = await self._analyze_parameter(
                strategy_factory=strategy_factory,
                base_params=base_params,
                param_name=param_name,
                values=values,
                data=data,
            )
            parameters[param_name] = sensitivity

        return SensitivityResult(
            parameters=parameters,
            baseline_result=baseline_result,
            base_params=base_params,
        )

    async def _analyze_parameter(
        self,
        strategy_factory: Callable[[dict[str, Any]], BaseStrategy],
        base_params: dict[str, Any],
        param_name: str,
        values: list[Any],
        data: MultiTimeframeData,
    ) -> ParameterSensitivity:
        """Run backtests for all values of a single parameter."""
        metrics_data: dict[str, list[float]] = {m: [] for m in self.config.metrics}

        for value in values:
            params = base_params.copy()
            params[param_name] = value

            strategy = strategy_factory(params)
            engine = MultiTimeframeBacktestEngine(config=self.config.backtest_config)
            result = await engine.run(strategy, data)

            for metric in self.config.metrics:
                val = getattr(result, metric, None)
                metrics_data[metric].append(float(val) if val is not None else 0.0)

        return ParameterSensitivity(
            param_name=param_name,
            values=values,
            metrics=metrics_data,
        )
