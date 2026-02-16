"""
Tests for GridOptimizer — two-phase parameter optimization.

Tests cover:
- Basic optimization run
- Objective functions (ROI, Sharpe, Calmar, Profit Factor)
- Two-phase (coarse + fine)
- Top-N extraction
- Parameter impact analysis
"""

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from bot.backtesting.grid.models import (
    CLUSTER_PRESETS,
    CoinCluster,
    ClusterPreset,
    GridBacktestConfig,
    OptimizationObjective,
)
from bot.backtesting.grid.optimizer import (
    GridOptimizationResult,
    GridOptimizer,
    OptimizationTrial,
)
from bot.strategies.grid.grid_calculator import GridSpacing


# =============================================================================
# Helpers
# =============================================================================


def make_ranging_candles(
    n: int = 100,
    center: float = 45000.0,
    spread: float = 500.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate ranging candles ideal for grid trading."""
    rng = np.random.RandomState(seed)
    rows = []
    prev = center
    for i in range(n):
        target = center + rng.uniform(-spread, spread)
        close = prev + (target - prev) * 0.3
        high = close + abs(rng.normal(0, spread * 0.1))
        low = close - abs(rng.normal(0, spread * 0.1))
        rows.append({
            "timestamp": f"2025-01-01T{i:04d}",
            "open": prev,
            "high": max(high, prev, close),
            "low": min(low, prev, close),
            "close": close,
            "volume": rng.uniform(100, 1000),
        })
        prev = close
    return pd.DataFrame(rows)


# =============================================================================
# Tests
# =============================================================================


class TestGridOptimizer:
    """Test grid parameter optimization."""

    def test_basic_optimization(self):
        """Optimizer runs coarse + fine phases and returns result."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=100)
        preset = ClusterPreset(
            cluster=CoinCluster.BLUE_CHIPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(8, 12),
            profit_per_grid_range=(0.003, 0.008),
        )

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            objective=OptimizationObjective.ROI,
            coarse_steps=3,
            fine_steps=3,
        )

        assert isinstance(result, GridOptimizationResult)
        assert result.best_trial is not None
        assert result.coarse_trials > 0
        assert result.fine_trials > 0
        assert len(result.all_trials) == result.coarse_trials + result.fine_trials
        assert result.total_duration_seconds > 0

    def test_different_objectives(self):
        """Optimizer works with all objective functions."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)
        preset = ClusterPreset(
            cluster=CoinCluster.MID_CAPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(5, 8),
            profit_per_grid_range=(0.005, 0.01),
        )

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
            assert result.best_trial is not None, f"No best trial for {obj}"
            assert len(result.all_trials) > 0

    def test_top_n_sorted(self):
        """top_n() returns trials sorted by objective descending."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=100)
        preset = CLUSTER_PRESETS[CoinCluster.BLUE_CHIPS]

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            objective=OptimizationObjective.ROI,
            coarse_steps=3,
            fine_steps=2,
        )

        top5 = result.top_n(5)
        assert len(top5) <= 5
        assert len(top5) > 0
        # Verify descending order
        for i in range(len(top5) - 1):
            assert top5[i].objective_value >= top5[i + 1].objective_value

    def test_param_impact_analysis(self):
        """param_impact() returns correlation values for each parameter."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=80)
        preset = ClusterPreset(
            cluster=CoinCluster.BLUE_CHIPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(6, 12),
            profit_per_grid_range=(0.002, 0.01),
        )

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            objective=OptimizationObjective.ROI,
            coarse_steps=3,
            fine_steps=2,
        )

        impact = result.param_impact()
        assert "num_levels" in impact
        assert "profit_per_grid" in impact
        for key, value in impact.items():
            assert 0 <= value <= 1.0, f"{key}: impact={value} out of [0,1]"

    def test_trial_to_dict(self):
        """Trial serializes to dict."""
        config = GridBacktestConfig(
            symbol="ETHUSDT",
            upper_price=Decimal("3000"),
            lower_price=Decimal("2500"),
            initial_balance=Decimal("5000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=30, center=2750.0, spread=200.0)
        preset = ClusterPreset(
            cluster=CoinCluster.BLUE_CHIPS,
            spacing_options=[GridSpacing.ARITHMETIC],
            levels_range=(5, 8),
            profit_per_grid_range=(0.003, 0.008),
        )

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            objective=OptimizationObjective.SHARPE,
            coarse_steps=2,
            fine_steps=2,
        )

        trial = result.best_trial
        d = trial.to_dict()
        assert "trial_id" in d
        assert "objective_value" in d
        assert "num_levels" in d
        assert "total_return_pct" in d

    def test_single_spacing_option(self):
        """Preset with single spacing works (no Cartesian explosion)."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=50)
        # Memes preset: geometric only
        preset = CLUSTER_PRESETS[CoinCluster.MEMES]

        optimizer = GridOptimizer()
        result = optimizer.optimize(
            base_config=config,
            candles=candles,
            preset=preset,
            objective=OptimizationObjective.ROI,
            coarse_steps=2,
            fine_steps=2,
        )

        assert result.best_trial is not None
        # All trials should use geometric spacing
        for trial in result.all_trials:
            assert trial.config.spacing == GridSpacing.GEOMETRIC
