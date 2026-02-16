"""
GridBacktestReporter — Report generation and preset export.

Generates:
- Summary reports from backtest results
- Optimization reports with parameter impact analysis
- JSON/YAML preset export compatible with GridStrategyConfig
"""

import json
from typing import Any

import yaml

from bot.backtesting.grid.models import GridBacktestResult
from bot.backtesting.grid.optimizer import GridOptimizationResult, OptimizationTrial


class GridBacktestReporter:
    """
    Generates reports and exports presets from backtest/optimization results.

    Usage:
        reporter = GridBacktestReporter()
        summary = reporter.generate_summary([result1, result2])
        yaml_str = reporter.export_preset_yaml(result)
    """

    def generate_summary(
        self,
        results: list[GridBacktestResult],
        top_n: int = 5,
    ) -> dict[str, Any]:
        """
        Generate summary report from multiple backtest results.

        Args:
            results: List of backtest results.
            top_n: Number of top results to include.

        Returns:
            Summary dict with rankings by ROI, Sharpe, drawdown.
        """
        if not results:
            return {"results": [], "count": 0}

        by_roi = sorted(results, key=lambda r: r.total_return_pct, reverse=True)
        by_sharpe = sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)
        by_drawdown = sorted(results, key=lambda r: r.max_drawdown_pct)

        return {
            "count": len(results),
            "top_by_roi": [r.to_dict() for r in by_roi[:top_n]],
            "top_by_sharpe": [r.to_dict() for r in by_sharpe[:top_n]],
            "lowest_drawdown": [r.to_dict() for r in by_drawdown[:top_n]],
            "avg_return_pct": sum(r.total_return_pct for r in results) / len(results),
            "avg_sharpe": sum(r.sharpe_ratio for r in results) / len(results),
            "avg_drawdown": sum(r.max_drawdown_pct for r in results) / len(results),
        }

    def generate_optimization_report(
        self,
        opt_result: GridOptimizationResult,
    ) -> dict[str, Any]:
        """
        Generate optimization report with parameter impact analysis.

        Args:
            opt_result: Optimization result.

        Returns:
            Report dict with best config, top trials, param impact.
        """
        report: dict[str, Any] = {
            "symbol": opt_result.symbol,
            "objective": opt_result.objective.value,
            "total_trials": len(opt_result.all_trials),
            "coarse_trials": opt_result.coarse_trials,
            "fine_trials": opt_result.fine_trials,
            "duration_seconds": round(opt_result.total_duration_seconds, 2),
        }

        if opt_result.best_trial:
            report["best_config"] = {
                "num_levels": opt_result.best_trial.config.num_levels,
                "spacing": opt_result.best_trial.config.spacing.value,
                "profit_per_grid": float(opt_result.best_trial.config.profit_per_grid),
                "amount_per_grid": float(opt_result.best_trial.config.amount_per_grid),
                "objective_value": round(opt_result.best_trial.objective_value, 6),
            }
            report["best_result"] = opt_result.best_trial.result.to_dict()

        report["top_5"] = [t.to_dict() for t in opt_result.top_n(5)]
        report["param_impact"] = opt_result.param_impact()

        return report

    def export_preset_json(self, result: GridBacktestResult) -> str:
        """
        Export backtest config as JSON preset for live bot.

        Args:
            result: Backtest result to export config from.

        Returns:
            JSON string compatible with GridStrategyConfig.
        """
        preset = self._build_preset_dict(result)
        return json.dumps(preset, indent=2)

    def export_preset_yaml(self, result: GridBacktestResult) -> str:
        """
        Export backtest config as YAML preset for live bot.

        Compatible with GridStrategyConfig.from_yaml().

        Args:
            result: Backtest result to export config from.

        Returns:
            YAML string.
        """
        preset = self._build_preset_dict(result)
        return yaml.safe_dump(preset, default_flow_style=False, sort_keys=False)

    # =========================================================================
    # Private
    # =========================================================================

    def _build_preset_dict(self, result: GridBacktestResult) -> dict[str, Any]:
        """Build a GridStrategyConfig-compatible dict from result config."""
        config = result.config
        preset: dict[str, Any] = {
            "symbol": config.symbol,
            "volatility_mode": "custom",
            "grid_spacing": config.spacing.value,
            "num_levels": config.num_levels,
            "amount_per_grid": str(config.amount_per_grid),
            "profit_per_grid": str(config.profit_per_grid),
            "atr_multiplier": str(config.atr_multiplier),
            "atr_period": config.atr_period,
        }

        # Add fixed bounds if specified
        if not config.auto_bounds:
            preset["upper_price"] = str(config.upper_price)
            preset["lower_price"] = str(config.lower_price)

        # Risk settings
        preset["risk"] = {
            "grid_stop_loss_pct": str(config.stop_loss_pct),
            "max_drawdown_pct": str(config.max_drawdown_pct),
        }

        # Backtest performance metadata (not part of GridStrategyConfig, but useful)
        preset["_backtest_metrics"] = {
            "total_return_pct": round(result.total_return_pct, 4),
            "sharpe_ratio": round(result.sharpe_ratio, 4),
            "max_drawdown_pct": round(result.max_drawdown_pct, 4),
            "completed_cycles": result.completed_cycles,
            "profit_factor": round(result.profit_factor, 4),
        }

        return preset
