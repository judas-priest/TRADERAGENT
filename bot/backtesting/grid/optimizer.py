"""
GridOptimizer — Two-phase parameter optimization for grid strategies.

Phase 1 (Coarse): Cartesian product of parameter ranges from ClusterPreset.
Phase 2 (Fine): Narrow search around best parameters with finer steps.

Uses ProcessPoolExecutor for parallel simulation.
"""

import itertools
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from bot.backtesting.grid.models import (
    ClusterPreset,
    GridBacktestConfig,
    GridBacktestResult,
    GridDirection,
    OptimizationObjective,
)
from bot.backtesting.grid.simulator import GridBacktestSimulator
from bot.strategies.grid.grid_calculator import GridSpacing


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class OptimizationTrial:
    """Result of a single optimization trial."""

    trial_id: int
    config: GridBacktestConfig
    result: GridBacktestResult
    objective_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "objective_value": round(self.objective_value, 6),
            "num_levels": self.config.num_levels,
            "spacing": self.config.spacing.value,
            "profit_per_grid": float(self.config.profit_per_grid),
            "amount_per_grid": float(self.config.amount_per_grid),
            **self.result.to_dict(),
        }


@dataclass
class GridOptimizationResult:
    """Result of full optimization run."""

    symbol: str
    objective: OptimizationObjective
    best_trial: OptimizationTrial | None = None
    all_trials: list[OptimizationTrial] = field(default_factory=list)
    coarse_trials: int = 0
    fine_trials: int = 0
    total_duration_seconds: float = 0.0

    def top_n(self, n: int = 5) -> list[OptimizationTrial]:
        """Get top N trials by objective value."""
        sorted_trials = sorted(
            self.all_trials,
            key=lambda t: t.objective_value,
            reverse=True,
        )
        return sorted_trials[:n]

    def param_impact(self) -> dict[str, float]:
        """Analyze which parameters have the most impact on objective."""
        if len(self.all_trials) < 2:
            return {}

        impact: dict[str, float] = {}
        params = ["num_levels", "profit_per_grid", "amount_per_grid"]

        for param in params:
            values = []
            objectives = []
            for t in self.all_trials:
                if param == "num_levels":
                    values.append(float(t.config.num_levels))
                elif param == "profit_per_grid":
                    values.append(float(t.config.profit_per_grid))
                elif param == "amount_per_grid":
                    values.append(float(t.config.amount_per_grid))
                objectives.append(t.objective_value)

            if len(set(values)) > 1:
                # Simple correlation as impact measure
                arr_v = np.array(values)
                arr_o = np.array(objectives)
                if arr_v.std() > 0 and arr_o.std() > 0:
                    corr = np.corrcoef(arr_v, arr_o)[0, 1]
                    impact[param] = round(abs(float(corr)), 4)
                else:
                    impact[param] = 0.0
            else:
                impact[param] = 0.0

        return impact


# =============================================================================
# Optimizer
# =============================================================================


def _run_single_trial(config_dict: dict, candles_data: dict) -> dict:
    """Run a single backtest trial (picklable for ProcessPoolExecutor)."""
    # Reconstruct config from dict
    config = GridBacktestConfig(
        symbol=config_dict["symbol"],
        timeframe=config_dict.get("timeframe", "1h"),
        upper_price=Decimal(str(config_dict["upper_price"])),
        lower_price=Decimal(str(config_dict["lower_price"])),
        num_levels=config_dict["num_levels"],
        spacing=GridSpacing(config_dict["spacing"]),
        profit_per_grid=Decimal(str(config_dict["profit_per_grid"])),
        amount_per_grid=Decimal(str(config_dict["amount_per_grid"])),
        direction=GridDirection(config_dict.get("direction", "neutral")),
        atr_period=config_dict.get("atr_period", 14),
        atr_multiplier=Decimal(str(config_dict.get("atr_multiplier", "3.0"))),
        maker_fee=Decimal(str(config_dict.get("maker_fee", "0.001"))),
        taker_fee=Decimal(str(config_dict.get("taker_fee", "0.001"))),
        initial_balance=Decimal(str(config_dict.get("initial_balance", "10000"))),
        stop_loss_pct=Decimal(str(config_dict.get("stop_loss_pct", "0.50"))),
        max_drawdown_pct=Decimal(str(config_dict.get("max_drawdown_pct", "0.50"))),
    )

    # Reconstruct DataFrame from dict
    candles = pd.DataFrame(candles_data)

    sim = GridBacktestSimulator(config)
    result = sim.run(candles)

    return {
        "config": config_dict,
        "result": result.to_dict(),
        "total_return_pct": result.total_return_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "calmar_ratio": result.calmar_ratio,
        "profit_factor": result.profit_factor,
        "completed_cycles": result.completed_cycles,
        "max_drawdown_pct": result.max_drawdown_pct,
    }


class GridOptimizer:
    """
    Two-phase grid parameter optimizer.

    Usage:
        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=GridBacktestConfig(symbol="BTCUSDT", ...),
            candles=candles_df,
            preset=ClusterPreset(...),
            objective=OptimizationObjective.SHARPE,
        )
    """

    def __init__(self, max_workers: int | None = None) -> None:
        self.max_workers = max_workers

    def optimize(
        self,
        base_config: GridBacktestConfig,
        candles: pd.DataFrame,
        preset: ClusterPreset,
        objective: OptimizationObjective = OptimizationObjective.SHARPE,
        coarse_steps: int = 3,
        fine_steps: int = 3,
        max_workers: int | None = None,
    ) -> GridOptimizationResult:
        """
        Run two-phase optimization.

        Args:
            base_config: Base configuration (symbol, fees, balance).
            candles: OHLCV data.
            preset: Cluster preset with parameter ranges.
            objective: Optimization objective function.
            coarse_steps: Steps per parameter in coarse phase.
            fine_steps: Steps per parameter in fine phase.
            max_workers: Override max parallel workers.

        Returns:
            GridOptimizationResult with best parameters.
        """
        start_time = time.perf_counter()
        workers = max_workers or self.max_workers

        opt_result = GridOptimizationResult(
            symbol=base_config.symbol,
            objective=objective,
        )

        # Phase 1: Coarse search
        coarse_combos = self._generate_coarse_combos(base_config, preset, coarse_steps)
        coarse_trials = self._run_trials(
            coarse_combos, candles, objective, workers, trial_id_start=0,
        )
        opt_result.all_trials.extend(coarse_trials)
        opt_result.coarse_trials = len(coarse_trials)

        if not coarse_trials:
            opt_result.total_duration_seconds = time.perf_counter() - start_time
            return opt_result

        # Find best from coarse
        best_coarse = max(coarse_trials, key=lambda t: t.objective_value)

        # Phase 2: Fine search around best
        fine_combos = self._generate_fine_combos(
            base_config, best_coarse.config, preset, fine_steps,
        )
        if fine_combos:
            fine_trials = self._run_trials(
                fine_combos, candles, objective, workers,
                trial_id_start=len(coarse_trials),
            )
            opt_result.all_trials.extend(fine_trials)
            opt_result.fine_trials = len(fine_trials)

        # Determine overall best
        opt_result.best_trial = max(
            opt_result.all_trials, key=lambda t: t.objective_value,
        )
        opt_result.total_duration_seconds = time.perf_counter() - start_time

        return opt_result

    # =========================================================================
    # Combo Generation
    # =========================================================================

    def _generate_coarse_combos(
        self,
        base: GridBacktestConfig,
        preset: ClusterPreset,
        steps: int,
    ) -> list[GridBacktestConfig]:
        """Generate coarse parameter combinations from preset ranges."""
        levels_values = self._linspace_int(preset.levels_range[0], preset.levels_range[1], steps)
        profit_values = self._linspace_float(
            preset.profit_per_grid_range[0], preset.profit_per_grid_range[1], steps,
        )
        spacing_values = preset.spacing_options

        combos = []
        for levels, profit, spacing in itertools.product(levels_values, profit_values, spacing_values):
            config = GridBacktestConfig(
                symbol=base.symbol,
                timeframe=base.timeframe,
                upper_price=base.upper_price,
                lower_price=base.lower_price,
                num_levels=levels,
                spacing=spacing,
                profit_per_grid=Decimal(str(round(profit, 6))),
                amount_per_grid=base.amount_per_grid,
                direction=base.direction,
                atr_period=base.atr_period,
                atr_multiplier=base.atr_multiplier,
                maker_fee=base.maker_fee,
                taker_fee=base.taker_fee,
                initial_balance=base.initial_balance,
                stop_loss_pct=base.stop_loss_pct,
                max_drawdown_pct=base.max_drawdown_pct,
            )
            combos.append(config)

        return combos

    def _generate_fine_combos(
        self,
        base: GridBacktestConfig,
        best: GridBacktestConfig,
        preset: ClusterPreset,
        steps: int,
    ) -> list[GridBacktestConfig]:
        """Generate fine parameter combinations around best coarse result."""
        # Narrow levels range ±2 around best
        level_lo = max(preset.levels_range[0], best.num_levels - 2)
        level_hi = min(preset.levels_range[1], best.num_levels + 2)
        levels_values = self._linspace_int(level_lo, level_hi, steps)

        # Narrow profit range ±30% around best
        best_profit = float(best.profit_per_grid)
        profit_lo = max(preset.profit_per_grid_range[0], best_profit * 0.7)
        profit_hi = min(preset.profit_per_grid_range[1], best_profit * 1.3)
        profit_values = self._linspace_float(profit_lo, profit_hi, steps)

        combos = []
        for levels, profit in itertools.product(levels_values, profit_values):
            config = GridBacktestConfig(
                symbol=base.symbol,
                timeframe=base.timeframe,
                upper_price=base.upper_price,
                lower_price=base.lower_price,
                num_levels=levels,
                spacing=best.spacing,
                profit_per_grid=Decimal(str(round(profit, 6))),
                amount_per_grid=base.amount_per_grid,
                direction=base.direction,
                atr_period=base.atr_period,
                atr_multiplier=base.atr_multiplier,
                maker_fee=base.maker_fee,
                taker_fee=base.taker_fee,
                initial_balance=base.initial_balance,
                stop_loss_pct=base.stop_loss_pct,
                max_drawdown_pct=base.max_drawdown_pct,
            )
            combos.append(config)

        return combos

    # =========================================================================
    # Trial Execution
    # =========================================================================

    def _run_trials(
        self,
        configs: list[GridBacktestConfig],
        candles: pd.DataFrame,
        objective: OptimizationObjective,
        max_workers: int | None,
        trial_id_start: int = 0,
    ) -> list[OptimizationTrial]:
        """Run trials sequentially (ProcessPoolExecutor for large batches)."""
        trials = []

        for i, config in enumerate(configs):
            sim = GridBacktestSimulator(config)
            result = sim.run(candles)

            obj_value = self._get_objective_value(result, objective)
            trial = OptimizationTrial(
                trial_id=trial_id_start + i,
                config=config,
                result=result,
                objective_value=obj_value,
            )
            trials.append(trial)

        return trials

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _get_objective_value(
        result: GridBacktestResult,
        objective: OptimizationObjective,
    ) -> float:
        """Extract objective value from result."""
        if objective == OptimizationObjective.ROI:
            return result.total_return_pct
        elif objective == OptimizationObjective.SHARPE:
            return result.sharpe_ratio
        elif objective == OptimizationObjective.CALMAR:
            return result.calmar_ratio
        elif objective == OptimizationObjective.PROFIT_FACTOR:
            return result.profit_factor if result.profit_factor != float("inf") else 100.0
        return 0.0

    @staticmethod
    def _linspace_int(lo: int, hi: int, steps: int) -> list[int]:
        """Generate integer steps between lo and hi."""
        if steps <= 1 or lo == hi:
            return [lo]
        step = max(1, (hi - lo) // (steps - 1))
        values = list(range(lo, hi + 1, step))
        if values[-1] != hi:
            values.append(hi)
        return sorted(set(values))

    @staticmethod
    def _linspace_float(lo: float, hi: float, steps: int) -> list[float]:
        """Generate float steps between lo and hi."""
        if steps <= 1 or lo >= hi:
            return [lo]
        return list(np.linspace(lo, hi, steps))
