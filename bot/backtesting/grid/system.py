"""
GridBacktestSystem — End-to-end grid backtesting pipeline.

Orchestrates:
1. Data loading (CSV or synthetic)
2. Coin classification (CoinClusterizer)
3. Parameter optimization (GridOptimizer)
4. Stress testing (volatile sub-periods)
5. Report generation + preset export (GridBacktestReporter)
"""

import time
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from bot.backtesting.grid.clusterizer import CoinClusterizer
from bot.backtesting.grid.models import (
    GridBacktestConfig,
    GridBacktestResult,
    GridDirection,
    OptimizationObjective,
)
from bot.backtesting.grid.optimizer import GridOptimizationResult, GridOptimizer
from bot.backtesting.grid.reporter import GridBacktestReporter
from bot.backtesting.grid.simulator import GridBacktestSimulator


class GridBacktestSystem:
    """
    End-to-end grid backtesting system.

    Usage:
        system = GridBacktestSystem()

        # Quick single run
        result = system.run_single_backtest(config, candles)

        # Full pipeline with optimization
        report = system.run_full_pipeline(
            symbols=["BTCUSDT", "ETHUSDT"],
            candles_map={"BTCUSDT": btc_df, "ETHUSDT": eth_df},
        )
    """

    def __init__(self) -> None:
        self.clusterizer = CoinClusterizer()
        self.optimizer = GridOptimizer()
        self.reporter = GridBacktestReporter()

    def run_single_backtest(
        self,
        config: GridBacktestConfig,
        candles: pd.DataFrame,
    ) -> GridBacktestResult:
        """
        Run a single backtest with given config.

        Args:
            config: Grid backtest configuration.
            candles: OHLCV DataFrame.

        Returns:
            GridBacktestResult.
        """
        sim = GridBacktestSimulator(config)
        return sim.run(candles)

    def run_full_pipeline(
        self,
        symbols: list[str],
        candles_map: dict[str, pd.DataFrame],
        base_config: GridBacktestConfig | None = None,
        objective: OptimizationObjective = OptimizationObjective.SHARPE,
        coarse_steps: int = 3,
        fine_steps: int = 3,
    ) -> dict[str, Any]:
        """
        Run full pipeline: classify → optimize → stress test → report.

        Args:
            symbols: List of trading pair symbols.
            candles_map: Symbol → OHLCV DataFrame mapping.
            base_config: Base config template (fees, balance, etc.).
            objective: Optimization objective.
            coarse_steps: Coarse optimization steps.
            fine_steps: Fine optimization steps.

        Returns:
            Pipeline report with per-symbol results.
        """
        start_time = time.perf_counter()

        if base_config is None:
            base_config = GridBacktestConfig(
                initial_balance=Decimal("10000"),
                stop_loss_pct=Decimal("0.50"),
                max_drawdown_pct=Decimal("0.50"),
            )

        pipeline_results: dict[str, Any] = {
            "symbols": symbols,
            "objective": objective.value,
            "per_symbol": {},
        }

        for symbol in symbols:
            candles = candles_map.get(symbol)
            if candles is None or len(candles) < 15:
                pipeline_results["per_symbol"][symbol] = {"error": "insufficient data"}
                continue

            # Step 1: Classify
            profile = self.clusterizer.classify(symbol, candles)

            # Step 2: Get preset for cluster
            preset = self.clusterizer.get_preset(profile.cluster)

            # Step 3: Optimize
            config = GridBacktestConfig(
                symbol=symbol,
                upper_price=base_config.upper_price,
                lower_price=base_config.lower_price,
                initial_balance=base_config.initial_balance,
                maker_fee=base_config.maker_fee,
                taker_fee=base_config.taker_fee,
                stop_loss_pct=base_config.stop_loss_pct,
                max_drawdown_pct=base_config.max_drawdown_pct,
            )

            opt_result = self.optimizer.optimize(
                base_config=config,
                candles=candles,
                preset=preset,
                objective=objective,
                coarse_steps=coarse_steps,
                fine_steps=fine_steps,
            )

            # Step 4: Stress test best config (if available)
            stress_results = []
            if opt_result.best_trial:
                stress_results = self.run_stress_tests(
                    opt_result.best_trial.config, candles,
                )

            # Step 5: Generate reports
            opt_report = self.reporter.generate_optimization_report(opt_result)

            preset_yaml = ""
            if opt_result.best_trial:
                preset_yaml = self.reporter.export_preset_yaml(
                    opt_result.best_trial.result,
                )

            pipeline_results["per_symbol"][symbol] = {
                "profile": {
                    "cluster": profile.cluster.value,
                    "atr_pct": round(profile.atr_pct, 4),
                    "volatility_score": profile.volatility_score,
                },
                "optimization": opt_report,
                "stress_test": {
                    "periods_tested": len(stress_results),
                    "results": [r.to_dict() for r in stress_results],
                },
                "preset_yaml": preset_yaml,
            }

        pipeline_results["total_duration"] = round(
            time.perf_counter() - start_time, 2,
        )

        return pipeline_results

    def run_stress_tests(
        self,
        config: GridBacktestConfig,
        candles: pd.DataFrame,
        num_periods: int = 3,
        period_length: int | None = None,
    ) -> list[GridBacktestResult]:
        """
        Run stress tests on volatile sub-periods.

        Automatically detects the most volatile periods in the data
        and runs the backtest on each.

        Args:
            config: Grid backtest configuration.
            candles: Full OHLCV DataFrame.
            num_periods: Number of volatile periods to test.
            period_length: Length of each sub-period (default: 1/4 of total).

        Returns:
            List of GridBacktestResult for each stress period.
        """
        if len(candles) < 20:
            return []

        if period_length is None:
            period_length = max(20, len(candles) // 4)

        # Find most volatile periods using rolling ATR proxy
        closes = candles["close"].astype(float).values
        highs = candles["high"].astype(float).values
        lows = candles["low"].astype(float).values

        # Rolling range as volatility proxy
        volatilities = []
        for i in range(len(candles) - period_length):
            period_range = (
                max(highs[i:i + period_length]) - min(lows[i:i + period_length])
            )
            avg_price = np.mean(closes[i:i + period_length])
            if avg_price > 0:
                volatilities.append((i, period_range / avg_price))
            else:
                volatilities.append((i, 0.0))

        if not volatilities:
            return []

        # Sort by volatility descending, pick top N non-overlapping
        volatilities.sort(key=lambda x: x[1], reverse=True)

        selected_starts: list[int] = []
        for start_idx, _vol in volatilities:
            # Check no overlap with already selected
            overlaps = False
            for existing in selected_starts:
                if abs(start_idx - existing) < period_length:
                    overlaps = True
                    break
            if not overlaps:
                selected_starts.append(start_idx)
            if len(selected_starts) >= num_periods:
                break

        results = []
        for start_idx in selected_starts:
            period_candles = candles.iloc[start_idx:start_idx + period_length].reset_index(drop=True)
            if len(period_candles) >= 2:
                sim = GridBacktestSimulator(config)
                result = sim.run(period_candles)
                results.append(result)

        return results
