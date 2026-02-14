"""
Integration tests — Strategy adapter end-to-end lifecycle.

Validates that all 4 adapters (SMC, TrendFollower, Grid, DCA) correctly
implement the BaseStrategy interface and can execute the full
analyze → signal → open → update → close pipeline with real OHLCV data.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import numpy as np
import pandas as pd
import pytest

from bot.strategies.base import (
    BaseMarketAnalysis,
    BaseSignal,
    BaseStrategy,
    ExitReason,
    PositionInfo,
    SignalDirection,
    StrategyPerformance,
)
from bot.strategies.dca_adapter import DCAAdapter
from bot.strategies.grid_adapter import GridAdapter
from bot.strategies.smc_adapter import SMCStrategyAdapter
from bot.strategies.trend_follower_adapter import TrendFollowerAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(
    n: int = 100,
    base: float = 45000.0,
    trend: str = "up",
    freq: str = "15min",
) -> pd.DataFrame:
    """Generate OHLCV DataFrame with a configurable trend."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq=freq)
    if trend == "up":
        closes = base + np.cumsum(rng.uniform(0.5, 5, n))
    elif trend == "down":
        closes = base - np.cumsum(rng.uniform(0.5, 5, n))
    else:  # sideways
        closes = base + rng.normal(0, 3, n)
    highs = closes + rng.uniform(5, 30, n)
    lows = closes - rng.uniform(5, 30, n)
    opens = closes + rng.normal(0, 5, n)
    volumes = rng.uniform(100, 1000, n)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )


def _make_dip_data(
    n: int = 100, base: float = 45000.0, dip_pct: float = 0.04
) -> pd.DataFrame:
    """Generate data with a clear price dip from recent high for DCA entry.

    Creates a flat-to-rising section for most of the data, then a sharp drop
    in the last 5 candles so the recent-20 high is well above the final close.
    """
    rng = np.random.default_rng(123)
    dates = pd.date_range("2024-01-01", periods=n, freq="15min")
    # Most candles: stable around base
    stable = np.full(n - 5, base) + rng.uniform(-10, 10, n - 5)
    # Last 5 candles: sharp drop
    peak = base
    drop_target = base * (1 - dip_pct)
    drop = np.linspace(peak, drop_target, 5)
    closes = np.concatenate([stable, drop])
    highs = closes + rng.uniform(5, 30, n)
    lows = closes - rng.uniform(5, 30, n)
    opens = closes + rng.normal(0, 5, n)
    volumes = rng.uniform(100, 1000, n)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )


# ===========================================================================
# SMC Adapter E2E
# ===========================================================================


class TestSMCAdapterE2E:
    """End-to-end tests for SMC Strategy Adapter."""

    def test_interface_compliance(self):
        adapter = SMCStrategyAdapter()
        assert isinstance(adapter, BaseStrategy)

    def test_strategy_name_and_type(self):
        adapter = SMCStrategyAdapter(name="smc-test")
        assert adapter.get_strategy_name() == "smc-test"
        assert adapter.get_strategy_type() == "smc"

    def test_analyze_market_returns_analysis(self):
        adapter = SMCStrategyAdapter()
        df_d1 = _make_ohlcv(n=50, freq="1D")
        df_h4 = _make_ohlcv(n=100, freq="4h")
        df_h1 = _make_ohlcv(n=200, freq="1h")
        df_m15 = _make_ohlcv(n=400, freq="15min")

        result = adapter.analyze_market(df_d1, df_h4, df_h1, df_m15)
        assert isinstance(result, BaseMarketAnalysis)
        assert result.strategy_type == "smc"
        assert result.trend in ("bullish", "bearish", "sideways", "unknown", "ranging")
        assert 0.0 <= result.trend_strength <= 1.0

    def test_analyze_market_pads_dataframes(self):
        """SMC adapter should pad if fewer than 4 DFs provided."""
        adapter = SMCStrategyAdapter()
        df = _make_ohlcv(n=200)
        # Providing only 1 DF — should pad to 4
        result = adapter.analyze_market(df)
        assert isinstance(result, BaseMarketAnalysis)

    def test_generate_signal_returns_none_or_signal(self):
        adapter = SMCStrategyAdapter()
        df = _make_ohlcv(n=200)
        adapter.analyze_market(df)
        result = adapter.generate_signal(df, Decimal("10000"))
        assert result is None or isinstance(result, BaseSignal)

    def test_open_and_close_position(self):
        adapter = SMCStrategyAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("44500"),
            take_profit=Decimal("46000"),
            confidence=0.8,
            timestamp=datetime.now(timezone.utc),
            strategy_type="smc",
        )
        pos_id = adapter.open_position(signal, Decimal("100"))
        assert len(pos_id) > 0

        positions = adapter.get_active_positions()
        assert len(positions) == 1
        assert positions[0].strategy_type == "smc"

        adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))
        assert len(adapter.get_active_positions()) == 0

    def test_update_positions_tp_hit(self):
        adapter = SMCStrategyAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("44500"),
            take_profit=Decimal("46000"),
            confidence=0.8,
            timestamp=datetime.now(timezone.utc),
            strategy_type="smc",
        )
        adapter.open_position(signal, Decimal("100"))
        df = _make_ohlcv(n=10)

        exits = adapter.update_positions(Decimal("46500"), df)
        assert len(exits) == 1
        assert exits[0][1] == ExitReason.TAKE_PROFIT

    def test_update_positions_sl_hit(self):
        adapter = SMCStrategyAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("44500"),
            take_profit=Decimal("46000"),
            confidence=0.8,
            timestamp=datetime.now(timezone.utc),
            strategy_type="smc",
        )
        adapter.open_position(signal, Decimal("100"))
        df = _make_ohlcv(n=10)

        exits = adapter.update_positions(Decimal("44000"), df)
        assert len(exits) == 1
        assert exits[0][1] == ExitReason.STOP_LOSS

    def test_performance_after_trade(self):
        adapter = SMCStrategyAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("44500"),
            take_profit=Decimal("46000"),
            confidence=0.8,
            timestamp=datetime.now(timezone.utc),
            strategy_type="smc",
        )
        pos_id = adapter.open_position(signal, Decimal("100"))
        adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))

        perf = adapter.get_performance()
        assert isinstance(perf, StrategyPerformance)
        assert perf.total_trades == 1
        assert perf.winning_trades == 1
        assert perf.total_pnl > 0

    def test_get_status(self):
        adapter = SMCStrategyAdapter()
        status = adapter.get_status()
        assert status["name"] == "smc-default"
        assert status["type"] == "smc"
        assert "performance" in status

    def test_reset(self):
        adapter = SMCStrategyAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("44500"),
            take_profit=Decimal("46000"),
            confidence=0.8,
            timestamp=datetime.now(timezone.utc),
            strategy_type="smc",
        )
        adapter.open_position(signal, Decimal("100"))
        adapter.reset()
        assert len(adapter.get_active_positions()) == 0

    def test_short_position_pnl(self):
        adapter = SMCStrategyAdapter()
        signal = BaseSignal(
            direction=SignalDirection.SHORT,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("45500"),
            take_profit=Decimal("44000"),
            confidence=0.8,
            timestamp=datetime.now(timezone.utc),
            strategy_type="smc",
        )
        pos_id = adapter.open_position(signal, Decimal("100"))
        adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("44000"))
        perf = adapter.get_performance()
        assert perf.total_pnl > 0


# ===========================================================================
# Grid Adapter E2E
# ===========================================================================


class TestGridAdapterE2E:
    """End-to-end tests for Grid Strategy Adapter."""

    def test_interface_compliance(self):
        adapter = GridAdapter()
        assert isinstance(adapter, BaseStrategy)

    def test_strategy_name_and_type(self):
        adapter = GridAdapter(name="grid-test")
        assert adapter.get_strategy_name() == "grid-test"
        assert adapter.get_strategy_type() == "grid"

    def test_analyze_market(self):
        adapter = GridAdapter()
        df = _make_ohlcv(n=50, trend="sideways")
        result = adapter.analyze_market(df)
        assert isinstance(result, BaseMarketAnalysis)
        assert result.strategy_type == "grid"
        assert result.volatility >= 0

    def test_analyze_creates_grid_levels(self):
        adapter = GridAdapter(num_levels=5)
        df = _make_ohlcv(n=50, trend="sideways")
        adapter.analyze_market(df)
        assert len(adapter._grid_levels) > 0

    def test_generate_signal_no_analysis(self):
        """Signal should be None if analyze_market hasn't been called."""
        adapter = GridAdapter()
        df = _make_ohlcv(n=50)
        result = adapter.generate_signal(df, Decimal("10000"))
        assert result is None

    def test_open_and_close_position(self):
        adapter = GridAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("43000"),
            take_profit=Decimal("45225"),
            confidence=0.6,
            timestamp=datetime.now(timezone.utc),
            strategy_type="grid",
            signal_reason="grid_buy_level",
        )
        pos_id = adapter.open_position(signal, Decimal("100"))
        assert len(adapter.get_active_positions()) == 1

        adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("45225"))
        assert len(adapter.get_active_positions()) == 0

    def test_update_positions_tp(self):
        adapter = GridAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("43000"),
            take_profit=Decimal("45225"),
            confidence=0.6,
            timestamp=datetime.now(timezone.utc),
            strategy_type="grid",
        )
        adapter.open_position(signal, Decimal("100"))
        df = _make_ohlcv(n=10)

        exits = adapter.update_positions(Decimal("45500"), df)
        assert len(exits) == 1
        assert exits[0][1] == ExitReason.TAKE_PROFIT

    def test_performance_after_trades(self):
        adapter = GridAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("43000"),
            take_profit=Decimal("45225"),
            confidence=0.6,
            timestamp=datetime.now(timezone.utc),
            strategy_type="grid",
        )
        pos_id = adapter.open_position(signal, Decimal("100"))
        adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("45225"))
        perf = adapter.get_performance()
        assert perf.total_trades == 1
        assert perf.winning_trades == 1

    def test_reset(self):
        adapter = GridAdapter()
        df = _make_ohlcv(n=50, trend="sideways")
        adapter.analyze_market(df)
        adapter.reset()
        assert len(adapter._grid_levels) == 0
        assert len(adapter.get_active_positions()) == 0


# ===========================================================================
# DCA Adapter E2E
# ===========================================================================


class TestDCAAdapterE2E:
    """End-to-end tests for DCA Strategy Adapter."""

    def test_interface_compliance(self):
        adapter = DCAAdapter()
        assert isinstance(adapter, BaseStrategy)

    def test_strategy_name_and_type(self):
        adapter = DCAAdapter(name="dca-test")
        assert adapter.get_strategy_name() == "dca-test"
        assert adapter.get_strategy_type() == "dca"

    def test_analyze_market(self):
        adapter = DCAAdapter()
        df = _make_dip_data(n=100)
        result = adapter.analyze_market(df)
        assert isinstance(result, BaseMarketAnalysis)
        assert result.strategy_type == "dca"
        assert "recent_high" in result.details

    def test_generate_signal_on_dip(self):
        """DCA should signal when price drops from recent high."""
        adapter = DCAAdapter(price_deviation_pct=Decimal("0.02"))
        df = _make_dip_data(n=100, dip_pct=0.04)  # 4% dip > 2% threshold
        adapter.analyze_market(df)
        result = adapter.generate_signal(df, Decimal("10000"))
        assert result is not None
        assert isinstance(result, BaseSignal)
        assert result.direction == SignalDirection.LONG
        assert result.signal_reason == "dca_price_drop"

    def test_no_signal_small_dip(self):
        """No signal when dip is below threshold."""
        adapter = DCAAdapter(price_deviation_pct=Decimal("0.05"))
        df = _make_dip_data(n=100, dip_pct=0.02)  # 2% dip < 5% threshold
        adapter.analyze_market(df)
        result = adapter.generate_signal(df, Decimal("10000"))
        assert result is None

    def test_no_duplicate_position(self):
        """DCA should not open a second position while one is active."""
        adapter = DCAAdapter(price_deviation_pct=Decimal("0.02"))
        df = _make_dip_data(n=100, dip_pct=0.04)
        adapter.analyze_market(df)

        signal = adapter.generate_signal(df, Decimal("10000"))
        assert signal is not None
        adapter.open_position(signal, Decimal("100"))

        # Second signal should be None
        signal2 = adapter.generate_signal(df, Decimal("10000"))
        assert signal2 is None

    def test_safety_order_averaging(self):
        """DCA should average down on safety order fills."""
        adapter = DCAAdapter(
            safety_step_pct=Decimal("0.01"),
            max_safety_orders=3,
        )
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("42000"),
            take_profit=Decimal("45675"),
            confidence=0.7,
            timestamp=datetime.now(timezone.utc),
            strategy_type="dca",
        )
        pos_id = adapter.open_position(signal, Decimal("100"))
        df = _make_ohlcv(n=10)

        # Price drops to trigger first safety order (1% below entry)
        trigger_price = Decimal("44550")  # 1% below 45000
        exits = adapter.update_positions(trigger_price, df)
        assert len(exits) == 0  # No exit, just safety order fill

        pos = adapter._positions[pos_id]
        assert pos["safety_orders_filled"] == 1
        assert pos["avg_price"] < Decimal("45000")  # Average should be lower

    def test_open_and_close_position(self):
        adapter = DCAAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("42000"),
            take_profit=Decimal("45675"),
            confidence=0.7,
            timestamp=datetime.now(timezone.utc),
            strategy_type="dca",
        )
        pos_id = adapter.open_position(signal, Decimal("100"))
        assert len(adapter.get_active_positions()) == 1

        adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("45675"))
        assert len(adapter.get_active_positions()) == 0

        perf = adapter.get_performance()
        assert perf.total_trades == 1
        assert perf.total_pnl > 0

    def test_performance_metadata(self):
        """DCA performance should include avg_safety_orders."""
        adapter = DCAAdapter()
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("42000"),
            take_profit=Decimal("45675"),
            confidence=0.7,
            timestamp=datetime.now(timezone.utc),
            strategy_type="dca",
        )
        pos_id = adapter.open_position(signal, Decimal("100"))
        adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("45675"))
        perf = adapter.get_performance()
        assert "avg_safety_orders" in perf.metadata

    def test_reset(self):
        adapter = DCAAdapter()
        df = _make_dip_data(n=100)
        adapter.analyze_market(df)
        adapter.reset()
        assert adapter._recent_high == Decimal("0")
        assert len(adapter.get_active_positions()) == 0


# ===========================================================================
# TrendFollower Adapter E2E
# ===========================================================================


class TestTrendFollowerAdapterE2E:
    """End-to-end tests for Trend-Follower Adapter."""

    def test_interface_compliance(self):
        adapter = TrendFollowerAdapter()
        assert isinstance(adapter, BaseStrategy)

    def test_strategy_name_and_type(self):
        adapter = TrendFollowerAdapter(name="tf-test")
        assert adapter.get_strategy_name() == "tf-test"
        assert adapter.get_strategy_type() == "trend_follower"

    def test_analyze_market(self):
        adapter = TrendFollowerAdapter()
        df = _make_ohlcv(n=100, trend="up")
        result = adapter.analyze_market(df)
        assert isinstance(result, BaseMarketAnalysis)
        assert result.strategy_type == "trend_follower"
        assert result.trend in ("bullish_trend", "bearish_trend", "sideways", "unknown", "bullish", "bearish")

    def test_generate_signal_returns_none_or_signal(self):
        adapter = TrendFollowerAdapter()
        df = _make_ohlcv(n=100, trend="up")
        adapter.analyze_market(df)
        result = adapter.generate_signal(df, Decimal("10000"))
        assert result is None or isinstance(result, BaseSignal)

    def test_get_status(self):
        adapter = TrendFollowerAdapter()
        status = adapter.get_status()
        assert status["name"] == "trend-follower-default"
        assert status["type"] == "trend_follower"

    def test_reset(self):
        adapter = TrendFollowerAdapter()
        df = _make_ohlcv(n=100)
        adapter.analyze_market(df)
        adapter.reset()
        assert adapter._last_analysis is None
        assert adapter._pending_signal is None


# ===========================================================================
# Cross-Adapter Tests
# ===========================================================================


class TestCrossAdapterConsistency:
    """Verify all adapters produce consistent types and interfaces."""

    @pytest.fixture
    def adapters(self) -> list[BaseStrategy]:
        return [
            SMCStrategyAdapter(name="smc"),
            TrendFollowerAdapter(name="tf"),
            GridAdapter(name="grid"),
            DCAAdapter(name="dca"),
        ]

    def test_all_return_base_market_analysis(self, adapters):
        df = _make_ohlcv(n=200)
        for adapter in adapters:
            result = adapter.analyze_market(df)
            assert isinstance(result, BaseMarketAnalysis), (
                f"{adapter.get_strategy_name()} did not return BaseMarketAnalysis"
            )

    def test_all_return_strategy_performance(self, adapters):
        for adapter in adapters:
            perf = adapter.get_performance()
            assert isinstance(perf, StrategyPerformance), (
                f"{adapter.get_strategy_name()} did not return StrategyPerformance"
            )

    def test_all_return_position_info_list(self, adapters):
        for adapter in adapters:
            positions = adapter.get_active_positions()
            assert isinstance(positions, list), (
                f"{adapter.get_strategy_name()} did not return list"
            )

    def test_all_have_get_status(self, adapters):
        for adapter in adapters:
            status = adapter.get_status()
            assert "name" in status
            assert "type" in status
            assert "performance" in status

    def test_all_support_reset(self, adapters):
        df = _make_ohlcv(n=200)
        for adapter in adapters:
            adapter.analyze_market(df)
            adapter.reset()  # Should not raise

    def test_position_lifecycle_all_adapters(self):
        """Every adapter should handle open → close lifecycle identically."""
        adapters = [
            SMCStrategyAdapter(name="smc"),
            GridAdapter(name="grid"),
            DCAAdapter(name="dca"),
        ]
        signal = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("45000"),
            stop_loss=Decimal("44000"),
            take_profit=Decimal("46000"),
            confidence=0.7,
            timestamp=datetime.now(timezone.utc),
            strategy_type="test",
        )

        for adapter in adapters:
            pos_id = adapter.open_position(signal, Decimal("100"))
            assert len(adapter.get_active_positions()) == 1, (
                f"{adapter.get_strategy_name()} failed open_position"
            )
            adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))
            assert len(adapter.get_active_positions()) == 0, (
                f"{adapter.get_strategy_name()} failed close_position"
            )
            assert adapter.get_performance().total_trades == 1, (
                f"{adapter.get_strategy_name()} failed performance tracking"
            )
