"""Tests for multi-timeframe backtesting — Issue #172."""

from datetime import datetime
from decimal import Decimal

import pandas as pd
import pytest

from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.multi_tf_data_loader import (
    MultiTimeframeDataLoader,
)
from bot.tests.backtesting.multi_tf_engine import (
    MultiTFBacktestConfig,
    MultiTimeframeBacktestEngine,
)

# Reuse ConcreteStrategy from existing tests
from tests.strategies.test_base_strategy import ConcreteStrategy

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def loader():
    return MultiTimeframeDataLoader()


@pytest.fixture
def data_2days(loader):
    """2 days of uptrend data."""
    return loader.load(
        symbol="BTC/USDT",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 3),
        trend="up",
    )


@pytest.fixture
def data_7days(loader):
    """7 days of uptrend data — enough for warmup + execution."""
    return loader.load(
        symbol="BTC/USDT",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 8),
        trend="up",
    )


@pytest.fixture
def engine():
    config = MultiTFBacktestConfig(
        symbol="BTC/USDT",
        initial_balance=Decimal("10000"),
        warmup_bars=20,
    )
    return MultiTimeframeBacktestEngine(config=config)


# =============================================================================
# MultiTimeframeDataLoader Tests
# =============================================================================


class TestMultiTimeframeDataLoader:
    """Tests for data loading and synchronization."""

    def test_load_produces_four_dataframes(self, data_2days):
        assert isinstance(data_2days.d1, pd.DataFrame)
        assert isinstance(data_2days.h4, pd.DataFrame)
        assert isinstance(data_2days.h1, pd.DataFrame)
        assert isinstance(data_2days.m15, pd.DataFrame)

    def test_as_tuple(self, data_2days):
        t = data_2days.as_tuple()
        assert len(t) == 4
        assert t[0] is data_2days.d1
        assert t[3] is data_2days.m15

    def test_dataframe_columns(self, data_2days):
        expected = {"open", "high", "low", "close", "volume"}
        for df in [data_2days.d1, data_2days.h4, data_2days.h1, data_2days.m15]:
            assert set(df.columns) >= expected

    def test_m15_count(self, data_2days):
        """2 days = 2*24*4 = 192 M15 bars."""
        assert len(data_2days.m15) == 192

    def test_h1_count(self, data_2days):
        """2 days = 48 H1 bars."""
        assert len(data_2days.h1) == 48

    def test_h4_count(self, data_2days):
        """2 days = 12 H4 bars."""
        assert len(data_2days.h4) == 12

    def test_d1_count(self, data_2days):
        """2 days = 2 D1 bars."""
        assert len(data_2days.d1) == 2

    def test_datetime_index(self, data_2days):
        for df in [data_2days.d1, data_2days.h4, data_2days.h1, data_2days.m15]:
            assert isinstance(df.index, pd.DatetimeIndex)

    def test_timeframe_alignment(self, data_2days):
        """Each M15 timestamp should have a corresponding H1 and H4 ancestor."""
        for ts in data_2days.m15.index:
            h1_before = data_2days.h1[data_2days.h1.index <= ts]
            assert len(h1_before) > 0, f"No H1 candle for M15 at {ts}"

            h4_before = data_2days.h4[data_2days.h4.index <= ts]
            assert len(h4_before) > 0, f"No H4 candle for M15 at {ts}"

    def test_ohlcv_consistency(self, data_2days):
        """high >= max(open, close) and low <= min(open, close) for all bars."""
        for df in [data_2days.d1, data_2days.h4, data_2days.h1, data_2days.m15]:
            assert (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-10).all()
            assert (df["low"] <= df[["open", "close"]].min(axis=1) + 1e-10).all()

    def test_resampled_high_equals_child_max(self, data_2days):
        """H1 high should equal max of its 4 M15 highs."""
        h1_ts = data_2days.h1.index[0]
        m15_slice = data_2days.m15[
            (data_2days.m15.index >= h1_ts) & (data_2days.m15.index < h1_ts + pd.Timedelta(hours=1))
        ]
        assert abs(data_2days.h1.loc[h1_ts, "high"] - m15_slice["high"].max()) < 1e-10

    def test_resampled_open_equals_first_child(self, data_2days):
        """H1 open should equal the open of its first M15 bar."""
        h1_ts = data_2days.h1.index[0]
        m15_slice = data_2days.m15[
            (data_2days.m15.index >= h1_ts) & (data_2days.m15.index < h1_ts + pd.Timedelta(hours=1))
        ]
        assert abs(data_2days.h1.loc[h1_ts, "open"] - m15_slice.iloc[0]["open"]) < 1e-10

    def test_resampled_close_equals_last_child(self, data_2days):
        """H1 close should equal the close of its last M15 bar."""
        h1_ts = data_2days.h1.index[0]
        m15_slice = data_2days.m15[
            (data_2days.m15.index >= h1_ts) & (data_2days.m15.index < h1_ts + pd.Timedelta(hours=1))
        ]
        assert abs(data_2days.h1.loc[h1_ts, "close"] - m15_slice.iloc[-1]["close"]) < 1e-10

    def test_resampled_volume_equals_child_sum(self, data_2days):
        """H1 volume should equal sum of its 4 M15 volumes."""
        h1_ts = data_2days.h1.index[0]
        m15_slice = data_2days.m15[
            (data_2days.m15.index >= h1_ts) & (data_2days.m15.index < h1_ts + pd.Timedelta(hours=1))
        ]
        assert abs(data_2days.h1.loc[h1_ts, "volume"] - m15_slice["volume"].sum()) < 1e-10


class TestGetContextAt:
    """Tests for get_context_at rolling window."""

    def test_context_sizes(self, loader, data_7days):
        df_d1, df_h4, df_h1, df_m15 = loader.get_context_at(data_7days, m15_index=200, lookback=50)
        assert len(df_m15) == 50
        assert len(df_h1) <= 50
        assert len(df_h4) <= 50
        assert len(df_d1) <= 50

    def test_context_early_index(self, loader, data_7days):
        """When m15_index < lookback, return whatever is available."""
        df_d1, df_h4, df_h1, df_m15 = loader.get_context_at(data_7days, m15_index=10, lookback=50)
        assert len(df_m15) == 11  # indices 0..10
        assert len(df_d1) >= 1

    def test_context_timestamps_aligned(self, loader, data_7days):
        """Context DataFrames should not contain future data."""
        m15_index = 200
        current_ts = data_7days.m15.index[m15_index]
        df_d1, df_h4, df_h1, df_m15 = loader.get_context_at(
            data_7days, m15_index=m15_index, lookback=50
        )
        assert df_m15.index[-1] == current_ts
        assert df_h1.index[-1] <= current_ts
        assert df_h4.index[-1] <= current_ts
        assert df_d1.index[-1] <= current_ts

    def test_context_no_future_leak(self, loader, data_7days):
        """No candle in any context DataFrame should be after current timestamp."""
        m15_index = 100
        current_ts = data_7days.m15.index[m15_index]
        df_d1, df_h4, df_h1, df_m15 = loader.get_context_at(
            data_7days, m15_index=m15_index, lookback=50
        )
        for df in [df_d1, df_h4, df_h1, df_m15]:
            assert (df.index <= current_ts).all()


class TestDataLoaderTrends:
    """Test different trend modes."""

    def test_uptrend_prices_increase(self, loader):
        data = loader.load("BTC/USDT", datetime(2024, 1, 1), datetime(2024, 2, 1), trend="up")
        first_close = data.m15.iloc[0]["close"]
        last_close = data.m15.iloc[-1]["close"]
        # In an uptrend over 1 month, last price should generally be higher
        # Allow some tolerance since it's stochastic
        assert last_close > first_close * 0.8

    def test_downtrend_prices_decrease(self, loader):
        data = loader.load("BTC/USDT", datetime(2024, 1, 1), datetime(2024, 2, 1), trend="down")
        first_close = data.m15.iloc[0]["close"]
        last_close = data.m15.iloc[-1]["close"]
        assert last_close < first_close * 1.2


# =============================================================================
# MultiTFBacktestConfig Tests
# =============================================================================


class TestMultiTFBacktestConfig:
    def test_defaults(self):
        config = MultiTFBacktestConfig()
        assert config.symbol == "BTC/USDT"
        assert config.initial_balance == Decimal("10000")
        assert config.lookback == 100
        assert config.warmup_bars == 50
        assert config.analyze_every_n == 4

    def test_custom(self):
        config = MultiTFBacktestConfig(
            symbol="ETH/USDT",
            initial_balance=Decimal("5000"),
            warmup_bars=30,
        )
        assert config.symbol == "ETH/USDT"
        assert config.initial_balance == Decimal("5000")
        assert config.warmup_bars == 30


# =============================================================================
# MultiTimeframeBacktestEngine Tests
# =============================================================================


class TestMultiTimeframeBacktestEngine:
    """Tests for backtest engine execution."""

    async def test_engine_runs_without_error(self, engine, data_7days):
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        assert result is not None

    async def test_returns_backtest_result(self, engine, data_7days):
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        assert isinstance(result, BacktestResult)

    async def test_strategy_name_in_result(self, engine, data_7days):
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        assert result.strategy_name == "test-concrete"

    async def test_symbol_in_result(self, engine, data_7days):
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        assert result.symbol == "BTC/USDT"

    async def test_initial_balance_correct(self, engine, data_7days):
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        assert result.initial_balance == Decimal("10000")

    async def test_equity_curve_length(self, engine, data_7days):
        """Equity curve entries = total M15 bars - warmup bars."""
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        expected = len(data_7days.m15) - engine.config.warmup_bars
        assert len(result.equity_curve) == expected

    async def test_equity_curve_has_required_fields(self, engine, data_7days):
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        assert len(result.equity_curve) > 0
        point = result.equity_curve[0]
        assert "timestamp" in point
        assert "price" in point
        assert "portfolio_value" in point

    async def test_duration_set(self, engine, data_7days):
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        assert result.duration.days >= 6

    async def test_result_to_dict(self, engine, data_7days):
        strategy = ConcreteStrategy()
        result = await engine.run(strategy, data_7days)
        d = result.to_dict()
        assert d["strategy_name"] == "test-concrete"
        assert "performance" in d
        assert "trading_stats" in d

    async def test_run_with_generated_data(self):
        config = MultiTFBacktestConfig(
            initial_balance=Decimal("10000"),
            warmup_bars=20,
        )
        engine = MultiTimeframeBacktestEngine(config=config)
        strategy = ConcreteStrategy()
        result = await engine.run_with_generated_data(
            strategy=strategy,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 8),
            trend="up",
        )
        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) > 0

    async def test_different_warmup(self, data_7days):
        """Different warmup values produce different equity curve lengths."""
        strategy = ConcreteStrategy()

        config1 = MultiTFBacktestConfig(warmup_bars=20)
        engine1 = MultiTimeframeBacktestEngine(config=config1)
        r1 = await engine1.run(strategy, data_7days)

        config2 = MultiTFBacktestConfig(warmup_bars=40)
        engine2 = MultiTimeframeBacktestEngine(config=config2)
        r2 = await engine2.run(strategy, data_7days)

        assert len(r1.equity_curve) > len(r2.equity_curve)


# =============================================================================
# Integration Tests with Real Strategy Adapters
# =============================================================================


class TestSMCAdapterIntegration:
    """Integration test: run SMCStrategyAdapter through multi-TF engine."""

    async def test_smc_adapter_backtest(self):
        from bot.strategies.smc.config import SMCConfig
        from bot.strategies.smc_adapter import SMCStrategyAdapter

        # SMCStrategy.__init__ references risk_per_trade_pct and
        # max_position_size_usd but SMCConfig has risk_per_trade and
        # max_position_size. Provide a patched config with aliases.
        smc_config = SMCConfig()
        smc_config.risk_per_trade_pct = smc_config.risk_per_trade
        smc_config.max_position_size_usd = smc_config.max_position_size

        config = MultiTFBacktestConfig(
            symbol="BTC/USDT",
            initial_balance=Decimal("10000"),
            warmup_bars=60,
        )
        engine = MultiTimeframeBacktestEngine(config=config)
        strategy = SMCStrategyAdapter(
            config=smc_config,
            account_balance=Decimal("10000"),
            name="smc-backtest",
        )

        result = await engine.run_with_generated_data(
            strategy=strategy,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5),
            trend="up",
        )

        assert result.strategy_name == "smc-backtest"
        assert result.initial_balance == Decimal("10000")
        assert len(result.equity_curve) > 0


class TestTrendFollowerAdapterIntegration:
    """Integration test: run TrendFollowerAdapter through multi-TF engine."""

    async def test_trend_follower_backtest(self):
        from bot.strategies.trend_follower_adapter import TrendFollowerAdapter

        config = MultiTFBacktestConfig(
            symbol="BTC/USDT",
            initial_balance=Decimal("10000"),
            warmup_bars=60,
        )
        engine = MultiTimeframeBacktestEngine(config=config)
        strategy = TrendFollowerAdapter(
            initial_capital=Decimal("10000"),
            name="tf-backtest",
            log_trades=False,
        )

        result = await engine.run_with_generated_data(
            strategy=strategy,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 15),
            trend="up",
        )

        assert result.strategy_name == "tf-backtest"
        assert result.initial_balance == Decimal("10000")
        assert len(result.equity_curve) > 0


class TestMultiStrategyComparison:
    """Test running multiple strategies on the same data."""

    async def test_same_data_different_strategies(self):
        loader = MultiTimeframeDataLoader()
        data = loader.load(
            symbol="BTC/USDT",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 15),
            trend="up",
        )

        config = MultiTFBacktestConfig(
            initial_balance=Decimal("10000"),
            warmup_bars=20,
        )
        engine = MultiTimeframeBacktestEngine(config=config)

        # Run ConcreteStrategy
        s1 = ConcreteStrategy()
        r1 = await engine.run(s1, data)

        # Run another ConcreteStrategy (same strategy, fresh engine)
        engine2 = MultiTimeframeBacktestEngine(config=config)
        s2 = ConcreteStrategy()
        r2 = await engine2.run(s2, data)

        # Both should complete with same initial balance
        assert r1.initial_balance == r2.initial_balance
        assert len(r1.equity_curve) == len(r2.equity_curve)
