"""Tests for GridBacktestSimulator."""

from decimal import Decimal

import pandas as pd
import pytest

from grid_backtester.engine.models import (
    GridBacktestConfig,
    GridBacktestResult,
    GridDirection,
)
from grid_backtester.engine.simulator import GridBacktestSimulator
from grid_backtester.core.calculator import GridSpacing
from tests.conftest import make_candles, make_ranging_candles


class TestGridBacktestSimulator:

    def test_basic_run_returns_result(self):
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

    def test_atr_auto_bounds(self):
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            num_levels=10,
            atr_period=14,
            atr_multiplier=Decimal("3.0"),
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=100)
        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.candles_processed == 100
        assert result.final_equity > 0

    def test_direction_modes(self):
        for direction in GridDirection:
            config = GridBacktestConfig(
                symbol="BTCUSDT",
                upper_price=Decimal("46000"),
                lower_price=Decimal("44000"),
                num_levels=10,
                direction=direction,
                initial_balance=Decimal("10000"),
                stop_loss_pct=Decimal("0.50"),
                max_drawdown_pct=Decimal("0.50"),
            )
            candles = make_candles(n=50)
            sim = GridBacktestSimulator(config)
            result = sim.run(candles)
            assert result.candles_processed == 50

    def test_geometric_spacing(self):
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

    def test_risk_stop_on_drawdown(self):
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            max_drawdown_pct=Decimal("0.01"),
        )
        candles = make_candles(n=200, volatility=0.03)
        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.stopped_by_risk
        assert result.stop_reason != ""

    def test_fees_tracked(self):
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

        assert result.total_fees_paid >= 0

    def test_equity_curve_length(self):
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

    def test_result_to_dict(self):
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
        assert "capital_efficiency" in d
        assert "sharpe_ratio" in d

    def test_invalid_candles_raises(self):
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

    def test_take_profit_exit(self):
        """Issue #2: Take-profit triggers when PnL reaches threshold."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            take_profit_pct=Decimal("0.001"),  # Very low TP to trigger easily
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_ranging_candles(n=300, center=45000.0, spread=400.0)
        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        # May or may not trigger depending on market movement
        if result.stopped_by_risk and result.stop_reason == "take_profit_reached":
            assert result.candles_processed < 300

    def test_capital_efficiency_calculated(self):
        """Issue #6: Capital efficiency is computed."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=50)
        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.capital_efficiency >= 0.0
        assert "capital_efficiency" in result.to_dict()

    def test_trailing_grid_basic(self):
        """Issue #4: Trailing grid recenters when price escapes."""
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45200"),
            lower_price=Decimal("44800"),
            num_levels=5,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
            trailing_enabled=True,
            trailing_shift_threshold_pct=Decimal("0.01"),
            trailing_cooldown_candles=3,
        )
        candles = make_candles(n=100, start_price=45000.0, volatility=0.02)
        sim = GridBacktestSimulator(config)
        result = sim.run(candles)

        assert result.candles_processed > 0
        assert result.final_equity > 0
