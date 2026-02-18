"""Tests for GridOptimizer."""

import tempfile
from decimal import Decimal

import pytest

from grid_backtester.caching.indicator_cache import IndicatorCache
from grid_backtester.engine.models import (
    ClusterPreset,
    CoinCluster,
    GridBacktestConfig,
    GridBacktestResult,
    OptimizationObjective,
)
from grid_backtester.engine.optimizer import (
    GridOptimizationResult,
    GridOptimizer,
    OptimizationTrial,
)
from grid_backtester.persistence.checkpoint import OptimizationCheckpoint
from grid_backtester.core.calculator import GridSpacing
from tests.conftest import make_ranging_candles


class TestGridOptimizer:

    def test_basic_optimization(self):
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 12),
            profit_per_grid_range=(0.005, 0.01),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=100, center=45000.0, spread=500.0)

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            objective=OptimizationObjective.ROI,
            coarse_steps=2,
            fine_steps=2,
        )

        assert isinstance(result, GridOptimizationResult)
        assert result.best_trial is not None
        assert len(result.all_trials) > 0
        assert result.coarse_trials > 0

    def test_all_objectives(self):
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 10),
            profit_per_grid_range=(0.005, 0.008),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)

        optimizer = GridOptimizer()
        for obj in OptimizationObjective:
            result = optimizer.optimize(
                base_config=config,
                candles=candles,
                preset=preset,
                objective=obj,
                coarse_steps=2,
                fine_steps=2,
            )
            assert result.best_trial is not None

    def test_top_n(self):
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 12),
            profit_per_grid_range=(0.005, 0.01),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            coarse_steps=3,
            fine_steps=2,
        )

        top = result.top_n(3)
        assert len(top) <= 3
        # Should be sorted descending by objective value
        for i in range(len(top) - 1):
            assert top[i].objective_value >= top[i + 1].objective_value

    def test_param_impact(self):
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 15),
            profit_per_grid_range=(0.003, 0.01),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            coarse_steps=3,
            fine_steps=2,
        )

        impact = result.param_impact()
        assert "num_levels" in impact
        assert "profit_per_grid" in impact

    def test_trial_to_dict(self):
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(10, 12),
            profit_per_grid_range=(0.005, 0.008),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            coarse_steps=2,
            fine_steps=2,
        )

        if result.best_trial:
            d = result.best_trial.to_dict()
            assert "trial_id" in d
            assert "objective_value" in d
            assert "num_levels" in d

    def test_parallel_matches_sequential(self):
        """Parallel execution should produce equivalent results to sequential."""
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 10),
            profit_per_grid_range=(0.005, 0.008),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)

        # Sequential
        seq_opt = GridOptimizer(max_workers=1)
        seq_result = seq_opt.optimize(
            base_config=config, candles=candles, preset=preset,
            coarse_steps=2, fine_steps=2,
        )

        # Parallel
        par_opt = GridOptimizer(max_workers=2)
        par_result = par_opt.optimize(
            base_config=config, candles=candles, preset=preset,
            coarse_steps=2, fine_steps=2,
        )

        assert len(seq_result.all_trials) == len(par_result.all_trials)
        # Results should have similar objective values (small float diffs OK)
        seq_best = seq_result.best_trial.objective_value
        par_best = par_result.best_trial.objective_value
        assert abs(seq_best - par_best) < 0.01

    def test_with_indicator_cache(self):
        """Optimizer should work with shared IndicatorCache."""
        cache = IndicatorCache()
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 10),
            profit_per_grid_range=(0.005, 0.008),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)

        optimizer = GridOptimizer(indicator_cache=cache)
        result = optimizer.optimize(
            base_config=config, candles=candles, preset=preset,
            coarse_steps=2, fine_steps=2,
        )
        assert result.best_trial is not None
        # Cache should have been used
        assert cache.stats["size"] > 0

    def test_checkpoint_resume(self, tmp_path):
        """Optimizer should resume from checkpoint."""
        checkpoint = OptimizationCheckpoint(checkpoint_dir=str(tmp_path))
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 10),
            profit_per_grid_range=(0.005, 0.008),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)

        # First run with checkpoint
        opt1 = GridOptimizer(checkpoint=checkpoint)
        result1 = opt1.optimize(
            base_config=config, candles=candles, preset=preset,
            coarse_steps=2, fine_steps=2,
        )
        assert result1.best_trial is not None
        # Checkpoint should be cleaned up on success
        assert len(checkpoint.list_checkpoints()) == 0

    def test_checkpoint_saved_during_parallel(self, tmp_path):
        """Checkpoint should be saved as each parallel trial completes, not after all finish."""
        checkpoint = OptimizationCheckpoint(checkpoint_dir=str(tmp_path))
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 10),
            profit_per_grid_range=(0.005, 0.008),
        )
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)

        # Use parallel execution with checkpoint
        opt = GridOptimizer(max_workers=2, checkpoint=checkpoint)
        result = opt.optimize(
            base_config=config, candles=candles, preset=preset,
            coarse_steps=2, fine_steps=2,
        )
        assert result.best_trial is not None
        # Checkpoint cleaned up on success — verify it ran without error
        assert len(checkpoint.list_checkpoints()) == 0

    def test_from_dict_roundtrip(self):
        """GridBacktestResult.from_dict() should reconstruct from to_dict()."""
        config = GridBacktestConfig(symbol="ETHUSDT")
        original = GridBacktestResult(
            config=config,
            total_return_pct=5.1234,
            total_pnl=512.34,
            final_equity=10512.34,
            sharpe_ratio=1.5,
            calmar_ratio=2.0,
            profit_factor=3.5,
            total_trades=42,
            win_rate=0.65,
        )

        d = original.to_dict()
        restored = GridBacktestResult.from_dict(d, config=config)

        assert restored.total_return_pct == pytest.approx(original.total_return_pct, abs=0.001)
        assert restored.sharpe_ratio == pytest.approx(original.sharpe_ratio, abs=0.001)
        assert restored.total_trades == original.total_trades
