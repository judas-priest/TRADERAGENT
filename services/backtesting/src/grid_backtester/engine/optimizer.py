"""
GridOptimizer — Two-phase parameter optimization for grid strategies.

Phase 1 (Coarse): Cartesian product of parameter ranges from ClusterPreset.
Phase 2 (Fine): Narrow search around best parameters with finer steps.

Uses ProcessPoolExecutor for parallel simulation (Issue #5).
"""

import itertools
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from grid_backtester.engine.models import (
    ClusterPreset,
    GridBacktestConfig,
    GridBacktestResult,
    GridDirection,
    OptimizationObjective,
)
from grid_backtester.engine.simulator import GridBacktestSimulator
from grid_backtester.core.calculator import GridSpacing
from grid_backtester.caching.indicator_cache import IndicatorCache
from grid_backtester.persistence.checkpoint import OptimizationCheckpoint
from grid_backtester.logging import get_logger

logger = get_logger(__name__)


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
# Standalone trial runner (picklable for ProcessPoolExecutor)
# =============================================================================


def _run_single_trial(config_dict: dict, candles_data: dict) -> dict:
    """Run a single backtest trial (picklable for ProcessPoolExecutor)."""
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
        take_profit_pct=Decimal(str(config_dict.get("take_profit_pct", "0"))),
    )

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
        "capital_efficiency": result.capital_efficiency,
    }


def _config_to_dict(config: GridBacktestConfig) -> dict:
    """Serialize GridBacktestConfig to a picklable dict."""
    return {
        "symbol": config.symbol,
        "timeframe": config.timeframe,
        "upper_price": str(config.upper_price),
        "lower_price": str(config.lower_price),
        "num_levels": config.num_levels,
        "spacing": config.spacing.value,
        "profit_per_grid": str(config.profit_per_grid),
        "amount_per_grid": str(config.amount_per_grid),
        "direction": config.direction.value if hasattr(config, "direction") else "neutral",
        "atr_period": config.atr_period,
        "atr_multiplier": str(config.atr_multiplier),
        "maker_fee": str(config.maker_fee),
        "taker_fee": str(config.taker_fee),
        "initial_balance": str(config.initial_balance),
        "stop_loss_pct": str(config.stop_loss_pct),
        "max_drawdown_pct": str(config.max_drawdown_pct),
        "take_profit_pct": str(config.take_profit_pct),
    }


# =============================================================================
# Optimizer
# =============================================================================


class GridOptimizer:
    """Two-phase grid parameter optimizer with parallel execution."""

    def __init__(
        self,
        max_workers: int | None = None,
        indicator_cache: IndicatorCache | None = None,
        checkpoint: OptimizationCheckpoint | None = None,
    ) -> None:
        self.max_workers = max_workers
        self.indicator_cache = indicator_cache
        self.checkpoint = checkpoint

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
        """Run two-phase optimization."""
        start_time = time.perf_counter()
        workers = max_workers or self.max_workers

        # Generate a run_id for checkpoint support
        import hashlib
        run_id_src = f"{base_config.symbol}:{objective.value}:{coarse_steps}:{fine_steps}"
        run_id = hashlib.sha256(run_id_src.encode()).hexdigest()[:12]

        # Load completed trials from checkpoint
        completed_hashes: dict[str, dict] = {}
        if self.checkpoint:
            completed_hashes = self.checkpoint.load_completed(run_id)

        logger.info(
            "Starting optimization",
            symbol=base_config.symbol,
            objective=objective.value,
            coarse_steps=coarse_steps,
            fine_steps=fine_steps,
            max_workers=workers,
            checkpoint_loaded=len(completed_hashes),
        )

        opt_result = GridOptimizationResult(
            symbol=base_config.symbol,
            objective=objective,
        )

        # Phase 1: Coarse search
        coarse_combos = self._generate_coarse_combos(base_config, preset, coarse_steps)
        logger.info("Phase 1: coarse search", combos=len(coarse_combos))

        coarse_trials = self._run_trials(
            coarse_combos, candles, objective, workers, trial_id_start=0,
            run_id=run_id, completed_hashes=completed_hashes,
        )
        opt_result.all_trials.extend(coarse_trials)
        opt_result.coarse_trials = len(coarse_trials)

        if not coarse_trials:
            opt_result.total_duration_seconds = time.perf_counter() - start_time
            logger.warning("No coarse trials completed")
            return opt_result

        best_coarse = max(coarse_trials, key=lambda t: t.objective_value)
        logger.info(
            "Phase 1 complete",
            best_objective=round(best_coarse.objective_value, 4),
            trials=len(coarse_trials),
        )

        # Phase 2: Fine search around best
        fine_combos = self._generate_fine_combos(
            base_config, best_coarse.config, preset, fine_steps,
        )
        if fine_combos:
            logger.info("Phase 2: fine search", combos=len(fine_combos))
            fine_trials = self._run_trials(
                fine_combos, candles, objective, workers,
                trial_id_start=len(coarse_trials),
                run_id=run_id, completed_hashes=completed_hashes,
            )
            opt_result.all_trials.extend(fine_trials)
            opt_result.fine_trials = len(fine_trials)

        opt_result.best_trial = max(
            opt_result.all_trials, key=lambda t: t.objective_value,
        )
        opt_result.total_duration_seconds = time.perf_counter() - start_time

        # Cleanup checkpoint on success
        if self.checkpoint:
            self.checkpoint.cleanup(run_id)

        logger.info(
            "Optimization complete",
            symbol=base_config.symbol,
            total_trials=len(opt_result.all_trials),
            best_objective=round(opt_result.best_trial.objective_value, 4),
            duration_s=round(opt_result.total_duration_seconds, 2),
        )

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
                take_profit_pct=base.take_profit_pct,
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
        level_lo = max(preset.levels_range[0], best.num_levels - 2)
        level_hi = min(preset.levels_range[1], best.num_levels + 2)
        levels_values = self._linspace_int(level_lo, level_hi, steps)

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
                take_profit_pct=base.take_profit_pct,
            )
            combos.append(config)

        return combos

    # =========================================================================
    # Trial Execution (Issue #5: Parallel)
    # =========================================================================

    def _run_trials(
        self,
        configs: list[GridBacktestConfig],
        candles: pd.DataFrame,
        objective: OptimizationObjective,
        max_workers: int | None,
        trial_id_start: int = 0,
        run_id: str | None = None,
        completed_hashes: dict[str, dict] | None = None,
    ) -> list[OptimizationTrial]:
        """Run trials, using ProcessPoolExecutor when max_workers > 1."""
        if max_workers and max_workers > 1 and len(configs) > 1:
            return self._run_trials_parallel(
                configs, candles, objective, max_workers, trial_id_start,
                run_id=run_id, completed_hashes=completed_hashes,
            )
        return self._run_trials_sequential(
            configs, candles, objective, trial_id_start,
            run_id=run_id, completed_hashes=completed_hashes,
        )

    def _run_trials_sequential(
        self,
        configs: list[GridBacktestConfig],
        candles: pd.DataFrame,
        objective: OptimizationObjective,
        trial_id_start: int = 0,
        run_id: str | None = None,
        completed_hashes: dict[str, dict] | None = None,
    ) -> list[OptimizationTrial]:
        """Run trials sequentially."""
        trials = []
        completed_hashes = completed_hashes or {}

        for i, config in enumerate(configs):
            # Check checkpoint for already-completed trials
            if self.checkpoint and run_id and completed_hashes:
                config_dict = _config_to_dict(config)
                ch = OptimizationCheckpoint.config_hash(config_dict)
                if ch in completed_hashes:
                    result = GridBacktestResult.from_dict(completed_hashes[ch], config=config)
                    obj_value = self._get_objective_value(result, objective)
                    trial = OptimizationTrial(
                        trial_id=trial_id_start + i,
                        config=config,
                        result=result,
                        objective_value=obj_value,
                    )
                    trials.append(trial)
                    continue

            sim = GridBacktestSimulator(config, indicator_cache=self.indicator_cache)
            result = sim.run(candles)

            obj_value = self._get_objective_value(result, objective)
            trial = OptimizationTrial(
                trial_id=trial_id_start + i,
                config=config,
                result=result,
                objective_value=obj_value,
            )
            trials.append(trial)

            # Save to checkpoint
            if self.checkpoint and run_id:
                config_dict = _config_to_dict(config)
                ch = OptimizationCheckpoint.config_hash(config_dict)
                self.checkpoint.save_trial(run_id, trial_id_start + i, ch, result.to_dict())

        return trials

    def _run_trials_parallel(
        self,
        configs: list[GridBacktestConfig],
        candles: pd.DataFrame,
        objective: OptimizationObjective,
        max_workers: int,
        trial_id_start: int = 0,
        run_id: str | None = None,
        completed_hashes: dict[str, dict] | None = None,
    ) -> list[OptimizationTrial]:
        """Run trials in parallel using ProcessPoolExecutor (Issue #5)."""
        completed_hashes = completed_hashes or {}
        candles_data = candles.to_dict(orient="list")
        config_dicts = [_config_to_dict(c) for c in configs]

        # Separate already-completed from new trials
        cached_trials: list[OptimizationTrial] = []
        new_indices: list[int] = []

        for i, config in enumerate(configs):
            if completed_hashes:
                ch = OptimizationCheckpoint.config_hash(config_dicts[i])
                if ch in completed_hashes:
                    result = GridBacktestResult.from_dict(completed_hashes[ch], config=config)
                    obj_value = self._get_objective_value(result, objective)
                    cached_trials.append(OptimizationTrial(
                        trial_id=trial_id_start + i,
                        config=config,
                        result=result,
                        objective_value=obj_value,
                    ))
                    continue
            new_indices.append(i)

        logger.info(
            "Running parallel trials",
            total=len(configs),
            cached=len(cached_trials),
            new=len(new_indices),
            workers=max_workers,
        )

        results_map: dict[int, dict] = {}

        if new_indices:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {
                    executor.submit(_run_single_trial, config_dicts[idx], candles_data): idx
                    for idx in new_indices
                }

                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        results_map[idx] = future.result()
                    except Exception as e:
                        logger.error("Trial failed", trial_idx=idx, error=str(e))

        # Reconstruct OptimizationTrial objects from serialized results
        new_trials = []
        for i in new_indices:
            if i not in results_map:
                continue

            config = configs[i]
            trial_data = results_map[i]
            result = GridBacktestResult.from_dict(trial_data["result"], config=config)

            obj_value = self._get_objective_value(result, objective)
            trial = OptimizationTrial(
                trial_id=trial_id_start + i,
                config=config,
                result=result,
                objective_value=obj_value,
            )
            new_trials.append(trial)

            # Save to checkpoint
            if self.checkpoint and run_id:
                ch = OptimizationCheckpoint.config_hash(config_dicts[i])
                self.checkpoint.save_trial(run_id, trial_id_start + i, ch, result.to_dict())

        all_trials = cached_trials + new_trials
        logger.info("Parallel trials complete", successful=len(all_trials))
        return all_trials

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
        if steps <= 1 or lo == hi:
            return [lo]
        step = max(1, (hi - lo) // (steps - 1))
        values = list(range(lo, hi + 1, step))
        if values[-1] != hi:
            values.append(hi)
        return sorted(set(values))

    @staticmethod
    def _linspace_float(lo: float, hi: float, steps: int) -> list[float]:
        if steps <= 1 or lo >= hi:
            return [lo]
        return list(np.linspace(lo, hi, steps))
