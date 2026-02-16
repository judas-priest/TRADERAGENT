"""
Tests for GridBacktestSystem — end-to-end pipeline.

Tests cover:
- Single backtest run
- Full pipeline (classify → optimize → stress → report)
- Stress testing on volatile periods
- Preset export (JSON/YAML)
- Multi-symbol pipeline
"""

from decimal import Decimal

import numpy as np
import pandas as pd
import yaml

from bot.backtesting.grid.models import GridBacktestConfig, GridBacktestResult
from bot.backtesting.grid.system import GridBacktestSystem
from bot.strategies.grid.grid_calculator import GridSpacing


# =============================================================================
# Helpers
# =============================================================================


def make_candles(
    n: int = 200,
    center: float = 45000.0,
    spread: float = 500.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate ranging candles."""
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


def make_volatile_candles(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Generate candles with volatile periods (for stress testing)."""
    rng = np.random.RandomState(seed)
    rows = []
    prev = 45000.0
    for i in range(n):
        # Create 2 volatile bursts
        if 50 <= i < 80 or 130 <= i < 160:
            vol = 0.03  # 3% moves
        else:
            vol = 0.005  # 0.5% moves
        change = rng.normal(0, vol)
        close = prev * (1 + change)
        high = close * (1 + abs(rng.normal(0, vol / 2)))
        low = close * (1 - abs(rng.normal(0, vol / 2)))
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


class TestGridBacktestSystem:
    """Test end-to-end grid backtesting system."""

    def test_single_backtest(self):
        """run_single_backtest produces valid result."""
        system = GridBacktestSystem()
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=100)

        result = system.run_single_backtest(config, candles)

        assert isinstance(result, GridBacktestResult)
        assert result.candles_processed == 100
        assert result.final_equity > 0

    def test_full_pipeline_single_symbol(self):
        """Full pipeline for one symbol completes all stages."""
        system = GridBacktestSystem()
        candles = make_candles(n=100)

        report = system.run_full_pipeline(
            symbols=["BTCUSDT"],
            candles_map={"BTCUSDT": candles},
            coarse_steps=2,
            fine_steps=2,
        )

        assert "per_symbol" in report
        assert "BTCUSDT" in report["per_symbol"]

        btc = report["per_symbol"]["BTCUSDT"]
        assert "profile" in btc
        assert "optimization" in btc
        assert "stress_test" in btc
        assert "preset_yaml" in btc

        # Profile was classified
        assert btc["profile"]["cluster"] in ["blue_chips", "mid_caps", "memes", "stable"]

        # Optimization ran
        assert btc["optimization"]["total_trials"] > 0

        assert report["total_duration"] > 0

    def test_full_pipeline_multi_symbol(self):
        """Pipeline processes multiple symbols."""
        system = GridBacktestSystem()
        btc_candles = make_candles(n=100, center=45000.0, seed=42)
        eth_candles = make_candles(n=100, center=3000.0, spread=100.0, seed=43)

        report = system.run_full_pipeline(
            symbols=["BTCUSDT", "ETHUSDT"],
            candles_map={"BTCUSDT": btc_candles, "ETHUSDT": eth_candles},
            coarse_steps=2,
            fine_steps=2,
        )

        assert len(report["per_symbol"]) == 2
        assert "BTCUSDT" in report["per_symbol"]
        assert "ETHUSDT" in report["per_symbol"]

    def test_stress_testing(self):
        """Stress tests identify and run on volatile periods."""
        system = GridBacktestSystem()
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("48000"),
            lower_price=Decimal("42000"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_volatile_candles(n=200)

        results = system.run_stress_tests(config, candles, num_periods=2)

        assert len(results) > 0
        assert len(results) <= 2
        for r in results:
            assert isinstance(r, GridBacktestResult)
            assert r.candles_processed > 0

    def test_preset_export_yaml_valid(self):
        """Exported YAML preset is valid YAML with expected fields."""
        system = GridBacktestSystem()
        config = GridBacktestConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("45500"),
            lower_price=Decimal("44500"),
            num_levels=10,
            initial_balance=Decimal("10000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=50)

        result = system.run_single_backtest(config, candles)
        yaml_str = system.reporter.export_preset_yaml(result)

        # Should be valid YAML
        parsed = yaml.safe_load(yaml_str)
        assert parsed["symbol"] == "BTCUSDT"
        assert parsed["grid_spacing"] == "arithmetic"
        assert "num_levels" in parsed
        assert "risk" in parsed
        assert "_backtest_metrics" in parsed

    def test_preset_export_json_valid(self):
        """Exported JSON preset is valid JSON."""
        import json

        system = GridBacktestSystem()
        config = GridBacktestConfig(
            symbol="ETHUSDT",
            upper_price=Decimal("3100"),
            lower_price=Decimal("2900"),
            num_levels=8,
            initial_balance=Decimal("5000"),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )
        candles = make_candles(n=50, center=3000.0, spread=80.0)

        result = system.run_single_backtest(config, candles)
        json_str = system.reporter.export_preset_json(result)

        parsed = json.loads(json_str)
        assert parsed["symbol"] == "ETHUSDT"
        assert "num_levels" in parsed
        assert "profit_per_grid" in parsed

    def test_insufficient_data_handled(self):
        """Pipeline handles symbols with insufficient data gracefully."""
        system = GridBacktestSystem()
        short_candles = make_candles(n=5)

        report = system.run_full_pipeline(
            symbols=["SHORTDATA"],
            candles_map={"SHORTDATA": short_candles},
            coarse_steps=2,
            fine_steps=2,
        )

        assert "SHORTDATA" in report["per_symbol"]
        assert "error" in report["per_symbol"]["SHORTDATA"]
