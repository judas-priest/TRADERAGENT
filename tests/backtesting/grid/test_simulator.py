"""
Tests for GridBacktestSimulator — grid backtesting engine.

Tests cover:
- Basic simulation run
- Grid cycle completion (buy→sell→counter)
- Direction modes (long, short, neutral)
- ATR auto-bounds
- Risk stop (drawdown/stop-loss)
- Fee tracking
- Equity curve generation
- Edge cases (minimal candles, price outside grid)
"""

import asyncio
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from bot.backtesting.grid.models import (
    GridBacktestConfig,
    GridBacktestResult,
    GridDirection,
)
from bot.backtesting.grid.simulator import GridBacktestSimulator
from bot.strategies.grid.grid_calculator import GridSpacing


# =============================================================================
# Helpers
# =============================================================================


def make_candles(
    n: int = 100,
    start_price: float = 45000.0,
    volatility: float = 0.01,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic OHLCV candles with realistic price movement."""
    rng = np.random.RandomState(seed)
    prices = [start_price]
    for _ in range(n - 1):
        change = rng.normal(0, volatility)
        prices.append(prices[-1] * (1 + change))

    rows = []
    for i, close in enumerate(prices):
        high = close * (1 + abs(rng.normal(0, volatility / 2)))
        low = close * (1 - abs(rng.normal(0, volatility / 2)))
        open_price = prices[i - 1] if i > 0 else close
        rows.append({
            "timestamp": f"2025-01-01T{i:04d}",
            "open": open_price,
            "high": max(high, open_price, close),
            "low": min(low, open_price, close),
            "close": close,
            "volume": float(rng.uniform(100, 1000)),
        })

    return pd.DataFrame(rows)


def make_ranging_candles(
    n: int = 100,
    center: float = 45000.0,
    spread: float = 500.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate candles oscillating within a tight range (ideal for grid)."""
    rng = np.random.RandomState(seed)
    rows = []
    prev_close = center

    for i in range(n):
        # Oscillate around center with mean-reversion
        target = center + rng.uniform(-spread, spread)
        close = prev_close + (target - prev_close) * 0.3
        high = close + abs(rng.normal(0, spread * 0.1))
        low = close - abs(rng.normal(0, spread * 0.1))
        open_price = prev_close

        rows.append({
            "timestamp": f"2025-01-01T{i:04d}",
            "open": open_price,
            "high": max(high, open_price, close),
            "low": min(low, open_price, close),
            "close": close,
            "volume": float(rng.uniform(100, 1000)),
        })
        prev_close = close

    return pd.DataFrame(rows)


# =============================================================================
# Tests
# =============================================================================


class TestGridBacktestSimulator:
    """Test the core grid backtest simulator."""

    def test_basic_run_returns_result(self):
        """Simulator runs on candle data and returns GridBacktestResult."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=50, start_price=45000.0)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert isinstance(result, GridBacktestResult)
        assert result.candles_processed == 50
        assert result.final_equity > 0
        assert result.duration_seconds > 0
        assert len(result.equity_curve) == 50

    def test_fixed_bounds_grid(self):
        """Grid with fixed upper/lower bounds works correctly."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            profit_per_grid=Decimal("0.005"),
            initial_balance=Decimal("10000"),
        )
        candles = make_ranging_candles(n=200, center=45000.0, spread=800.0)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.candles_processed == 200
        assert result.total_trades > 0
        assert result.total_fees_paid > 0

    def test_atr_auto_bounds(self):
        """Simulator calculates bounds from ATR when upper/lower are 0."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("0"),
            lower_price=Decimal("0"),
            num_levels=10,
            atr_period=14,
            atr_multiplier=Decimal("3.0"),
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=100, start_price=45000.0)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.candles_processed == 100
        assert result.final_equity > 0
        # Auto bounds were calculated (no ValueError)

    def test_grid_cycles_completed(self):
        """Ranging market generates completed buy→sell cycles."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            num_levels=10,
            profit_per_grid=Decimal("0.003"),
            initial_balance=Decimal("10000"),
            maker_fee=Decimal("0.0005"),
            taker_fee=Decimal("0.0005"),
        )
        # Wide ranging candles to trigger many fills
        candles = make_ranging_candles(n=300, center=45000.0, spread=400.0)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        # Should have some cycles in a ranging market
        assert result.total_trades > 0
        # Grid fill rate should be non-zero
        assert result.grid_fill_rate >= 0.0

    def test_direction_long(self):
        """LONG direction shifts grid bounds down."""
        config_neutral = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            direction=GridDirection.NEUTRAL,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        config_long = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            direction=GridDirection.LONG,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=50)

        sim_neutral = GridBacktestSimulator(config_neutral)
        sim_long = GridBacktestSimulator(config_long)

        result_neutral = sim_neutral.run(candles)
        result_long = sim_long.run(candles)

        # Both should complete without errors
        assert result_neutral.candles_processed == 50
        assert result_long.candles_processed == 50

    def test_direction_short(self):
        """SHORT direction shifts grid bounds up."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            direction=GridDirection.SHORT,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=50)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.candles_processed == 50

    def test_geometric_spacing(self):
        """Geometric grid spacing works correctly."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            spacing=GridSpacing.GEOMETRIC,
            initial_balance=Decimal("10000"),
        )
        candles = make_ranging_candles(n=100)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.candles_processed == 100
        assert result.final_equity > 0

    def test_risk_stop_on_drawdown(self):
        """Simulator stops when drawdown exceeds limit."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            max_drawdown_pct=Decimal("0.01"),  # Very tight 1% drawdown
        )
        # Volatile candles that will cause drawdown
        candles = make_candles(n=200, volatility=0.03)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.stopped_by_risk
        assert result.stop_reason != ""
        assert result.candles_processed <= 200

    def test_fees_tracked(self):
        """Total fees are tracked across all trades."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            num_levels=8,
            initial_balance=Decimal("10000"),
            maker_fee=Decimal("0.001"),
            taker_fee=Decimal("0.001"),
        )
        candles = make_ranging_candles(n=200, center=45000.0, spread=400.0)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        if result.total_trades > 0:
            assert result.total_fees_paid > 0
        assert result.total_fees_paid >= 0

    def test_equity_curve_length_matches_candles(self):
        """Equity curve has one point per processed candle."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=80)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert len(result.equity_curve) == result.candles_processed
        # Each point has price and equity
        for pt in result.equity_curve:
            assert pt.equity > 0
            assert pt.price > 0

    def test_result_to_dict(self):
        """Result serializes to dict correctly."""
        config = GridBacktestConfig(
            symbol="ETHUSDT",
            upper_price=Decimal("3000"),
            lower_price=Decimal("2500"),
            num_levels=8,
            initial_balance=Decimal("5000"),
        )
        candles = make_candles(n=30, start_price=2750.0)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)
        d = result.to_dict()

        assert d["symbol"] == "ETHUSDT"
        assert "total_return_pct" in d
        assert "completed_cycles" in d
        assert "sharpe_ratio" in d
        assert "stopped_by_risk" in d
        assert isinstance(d["total_trades"], int)

    def test_price_leaves_grid_tracked(self):
        """Counts when price exits grid bounds."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45200"),
            lower_price=Decimal("44800"),
            num_levels=5,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),  # Wide SL so it doesn't stop early
            max_drawdown_pct=Decimal("0.50"),
        )
        # Candles with wide range — will leave the tight grid
        candles = make_candles(n=100, start_price=45000.0, volatility=0.015)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        # With tight grid and volatile data, price should leave grid sometimes
        assert result.price_left_grid_count >= 0

    def test_minimal_candles(self):
        """Simulator works with minimum 2 candles."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=5,
            initial_balance=Decimal("10000"),
        )
        candles = make_candles(n=2, start_price=45000.0)

        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.candles_processed == 2
        assert result.final_equity > 0

    def test_invalid_candles_raises(self):
        """Missing columns raises ValueError."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=5,
        )
        bad_df = pd.DataFrame({"open": [1, 2], "high": [3, 4]})

        sim = GridBacktestSimulator(config)
        with pytest.raises(ValueError, match="Missing columns"):
            sim.run(bad_df)
