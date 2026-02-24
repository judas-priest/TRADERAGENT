"""Tests for SMC strategy warmup_bars behaviour (#284)."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from bot.strategies.smc.config import SMCConfig
from bot.strategies.smc.smc_strategy import SMCStrategy


def _make_ohlcv_df(n: int = 200) -> pd.DataFrame:
    """Generate a minimal OHLCV DataFrame for testing."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 60000 + np.cumsum(np.random.randn(n) * 50)
    return pd.DataFrame(
        {
            "open": close - np.random.rand(n) * 20,
            "high": close + np.abs(np.random.randn(n)) * 30,
            "low": close - np.abs(np.random.randn(n)) * 30,
            "close": close,
            "volume": np.random.rand(n) * 1000 + 100,
        },
        index=dates,
    )


class TestSMCWarmup:
    """Verify warmup_bars skips signal generation for first N calls."""

    def test_default_warmup_bars_is_100(self) -> None:
        cfg = SMCConfig()
        assert cfg.warmup_bars == 100

    def test_custom_warmup_bars(self) -> None:
        cfg = SMCConfig(warmup_bars=50)
        assert cfg.warmup_bars == 50

    def test_generate_signals_returns_empty_during_warmup(self) -> None:
        cfg = SMCConfig(warmup_bars=3)
        strategy = SMCStrategy(config=cfg)
        df = _make_ohlcv_df()

        # First 3 calls should return empty (warmup)
        for i in range(3):
            result = strategy.generate_signals(df, df)
            assert result == [], f"Expected empty on call {i + 1} during warmup"

    def test_generate_signals_works_after_warmup(self) -> None:
        cfg = SMCConfig(warmup_bars=2)
        strategy = SMCStrategy(config=cfg)
        df = _make_ohlcv_df()

        # Warmup calls
        strategy.generate_signals(df, df)
        strategy.generate_signals(df, df)

        # After warmup, generate_signals should proceed to pattern detection
        # (may still return empty if no patterns found, but it should NOT
        # short-circuit — we verify the internal call count)
        assert strategy._generate_call_count == 2

        # Third call goes past warmup
        strategy.generate_signals(df, df)
        assert strategy._generate_call_count == 3

    def test_warmup_logged_only_once(self) -> None:
        cfg = SMCConfig(warmup_bars=5)
        strategy = SMCStrategy(config=cfg)
        df = _make_ohlcv_df()

        with patch("bot.strategies.smc.smc_strategy.logger") as mock_logger:
            for _ in range(5):
                strategy.generate_signals(df, df)

            # "smc_warmup_skip_N_bars" should be logged exactly once
            warmup_calls = [
                c
                for c in mock_logger.info.call_args_list
                if len(c.args) > 0 and "smc_warmup_skip_N_bars" in str(c.args[0])
            ]
            assert len(warmup_calls) == 1

    def test_reset_clears_warmup_counter(self) -> None:
        cfg = SMCConfig(warmup_bars=2)
        strategy = SMCStrategy(config=cfg)
        df = _make_ohlcv_df()

        # Exhaust warmup
        strategy.generate_signals(df, df)
        strategy.generate_signals(df, df)
        assert strategy._generate_call_count == 2

        # Reset
        strategy.reset()
        assert strategy._generate_call_count == 0
        assert strategy._warmup_logged is False

        # After reset, warmup applies again
        result = strategy.generate_signals(df, df)
        assert result == []
        assert strategy._generate_call_count == 1

    def test_warmup_zero_means_no_skip(self) -> None:
        """warmup_bars=0 means no warmup period."""
        cfg = SMCConfig(warmup_bars=0)
        strategy = SMCStrategy(config=cfg)
        df = _make_ohlcv_df()

        # Even first call should go past warmup check
        # (whether it returns signals depends on pattern detection)
        strategy.generate_signals(df, df)
        assert strategy._generate_call_count == 1
        # No warmup log should be emitted
        assert strategy._warmup_logged is False


class TestSMCConfigSchema:
    """Verify warmup_bars in the Pydantic config schema."""

    def test_warmup_bars_in_schema(self) -> None:
        from bot.config.schemas import SMCConfigSchema

        schema = SMCConfigSchema()
        assert schema.warmup_bars == 100

    def test_warmup_bars_custom_value(self) -> None:
        from bot.config.schemas import SMCConfigSchema

        schema = SMCConfigSchema(warmup_bars=200)
        assert schema.warmup_bars == 200
