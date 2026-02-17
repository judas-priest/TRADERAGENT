"""Tests for GridBacktestSystem."""

from decimal import Decimal

import pytest

from grid_backtester.engine.models import GridBacktestConfig, OptimizationObjective
from grid_backtester.engine.system import GridBacktestSystem
from tests.conftest import make_candles, make_ranging_candles


class TestGridBacktestSystem:

    def test_single_backtest(self):
        system = GridBacktestSystem()
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
        result = system.run_single_backtest(config, candles)

        assert result.candles_processed == 50
        assert result.final_equity > 0

    def test_full_pipeline(self):
        system = GridBacktestSystem()
        candles = make_ranging_candles(n=100, center=45000.0, spread=500.0)

        report = system.run_full_pipeline(
            symbols=["BTCUSDT"],
            candles_map={"BTCUSDT": candles},
            objective=OptimizationObjective.ROI,
            coarse_steps=2,
            fine_steps=2,
        )

        assert "per_symbol" in report
        assert "BTCUSDT" in report["per_symbol"]
        sym = report["per_symbol"]["BTCUSDT"]
        assert "profile" in sym
        assert "optimization" in sym
        assert "preset_yaml" in sym

    def test_pipeline_insufficient_data(self):
        system = GridBacktestSystem()
        import pandas as pd
        short = pd.DataFrame({
            "open": [1, 2], "high": [3, 4], "low": [0.5, 1],
            "close": [2, 3], "volume": [100, 200],
        })

        report = system.run_full_pipeline(
            symbols=["TESTUSDT"],
            candles_map={"TESTUSDT": short},
        )

        assert report["per_symbol"]["TESTUSDT"]["error"] == "insufficient data"

    def test_stress_tests(self):
        system = GridBacktestSystem()
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=200, volatility=0.02)
        results = system.run_stress_tests(config, candles, num_periods=2)

        assert len(results) <= 2
        for r in results:
            assert r.candles_processed > 0

    def test_multi_symbol_pipeline(self):
        system = GridBacktestSystem()
        btc_candles = make_ranging_candles(n=100, center=45000.0, spread=500.0)
        eth_candles = make_ranging_candles(n=100, center=3000.0, spread=50.0, seed=99)

        report = system.run_full_pipeline(
            symbols=["BTCUSDT", "ETHUSDT"],
            candles_map={"BTCUSDT": btc_candles, "ETHUSDT": eth_candles},
            coarse_steps=2,
            fine_steps=2,
        )

        assert "BTCUSDT" in report["per_symbol"]
        assert "ETHUSDT" in report["per_symbol"]
