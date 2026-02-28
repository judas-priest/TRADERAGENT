"""Integration tests for Trend-Follower Strategy with Bot Orchestrator"""

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from bot.strategies.trend_follower import TrendFollowerConfig, TrendFollowerStrategy
from bot.strategies.trend_follower.entry_logic import SignalType
from bot.strategies.trend_follower.market_analyzer import MarketPhase, TrendStrength


@pytest.fixture
def trend_follower_config():
    """Create Trend-Follower configuration for testing."""
    return TrendFollowerConfig(
        # Market analysis settings
        ema_fast_period=20,
        ema_slow_period=50,
        atr_period=14,
        rsi_period=14,
        # Entry settings
        volume_multiplier=Decimal("1.5"),
        max_atr_filter_pct=Decimal("0.05"),
        # Position management
        tp_multipliers=(Decimal("1.2"), Decimal("1.8"), Decimal("2.5")),
        sl_multipliers=(Decimal("0.7"), Decimal("1.0"), Decimal("1.0")),
        # Risk management
        risk_per_trade_pct=Decimal("0.02"),
        max_position_size_usd=Decimal("5000"),
        max_daily_loss_usd=Decimal("500"),
        max_positions=3,
        # Logging
        log_all_signals=False,
    )


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    periods = 200

    # Generate price data with trend
    base_price = 45000
    trend = np.linspace(0, 2000, periods)
    noise = np.random.normal(0, 200, periods)
    close_prices = base_price + trend + noise

    # Generate OHLC
    high_prices = close_prices + np.abs(np.random.normal(100, 50, periods))
    low_prices = close_prices - np.abs(np.random.normal(100, 50, periods))
    open_prices = close_prices + np.random.normal(0, 50, periods)

    # Generate volume
    volume = np.random.uniform(100, 1000, periods)

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2026-01-01", periods=periods, freq="1h"),
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volume,
        }
    )

    return df


@pytest.fixture
def trend_follower_strategy(trend_follower_config):
    """Create Trend-Follower Strategy instance."""
    return TrendFollowerStrategy(
        config=trend_follower_config, initial_capital=Decimal("10000"), log_trades=True
    )


@pytest.mark.asyncio
class TestTrendFollowerInitialization:
    """Test Trend-Follower Strategy initialization and setup."""

    def test_strategy_initialization(self, trend_follower_strategy, trend_follower_config):
        """Test that strategy initializes correctly with all components."""
        strategy = trend_follower_strategy

        assert strategy.config == trend_follower_config
        assert strategy.market_analyzer is not None
        assert strategy.entry_logic is not None
        assert strategy.position_manager is not None
        assert strategy.risk_manager is not None
        assert strategy.trade_logger is not None

    def test_components_initialized_with_config(
        self, trend_follower_strategy, trend_follower_config
    ):
        """Test that all components receive correct configuration."""
        strategy = trend_follower_strategy

        # Market analyzer should have correct periods
        assert strategy.market_analyzer.ema_fast_period == trend_follower_config.ema_fast_period
        assert strategy.market_analyzer.ema_slow_period == trend_follower_config.ema_slow_period
        assert strategy.market_analyzer.atr_period == trend_follower_config.atr_period

        # Risk manager should have correct limits
        assert strategy.risk_manager.risk_per_trade_pct == trend_follower_config.risk_per_trade_pct
        assert (
            strategy.risk_manager.max_position_size_usd
            == trend_follower_config.max_position_size_usd
        )


@pytest.mark.asyncio
class TestMarketAnalysisIntegration:
    """Test market analysis integration with main strategy."""

    def test_analyze_market_returns_conditions(self, trend_follower_strategy, sample_ohlcv_data):
        """Test that market analysis returns proper market conditions."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        conditions = strategy.analyze_market(df)

        # Should return market conditions
        assert conditions is not None
        assert hasattr(conditions, "phase")
        assert hasattr(conditions, "trend_strength")
        assert hasattr(conditions, "ema_fast")
        assert hasattr(conditions, "ema_slow")
        assert hasattr(conditions, "atr")
        assert hasattr(conditions, "rsi")

        # Values should be in expected ranges
        assert isinstance(conditions.phase, MarketPhase)
        assert isinstance(conditions.trend_strength, TrendStrength)
        assert conditions.atr > 0
        assert 0 <= conditions.rsi <= 100

    def test_market_conditions_stored_in_strategy(self, trend_follower_strategy, sample_ohlcv_data):
        """Test that market conditions are stored in strategy state."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        conditions = strategy.analyze_market(df)

        # Should be stored
        assert strategy.current_market_conditions == conditions


@pytest.mark.asyncio
class TestEntrySignalIntegration:
    """Test entry signal generation and integration."""

    def test_check_entry_signal_with_sufficient_balance(
        self, trend_follower_strategy, sample_ohlcv_data
    ):
        """Test entry signal checking with sufficient balance."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data
        current_balance = Decimal("10000")

        # First analyze market
        strategy.analyze_market(df)

        # Check for entry signal
        entry_data = strategy.check_entry_signal(df, current_balance)

        # May or may not have signal depending on data
        # But should return None or tuple of (signal, metrics, size)
        if entry_data:
            signal, metrics, position_size = entry_data
            assert signal is not None
            assert signal.signal_type in [SignalType.LONG, SignalType.SHORT]
            assert position_size > 0
            assert position_size <= strategy.config.max_position_size_usd

    def test_entry_signal_respects_risk_limits(self, trend_follower_strategy, sample_ohlcv_data):
        """Test that entry signals respect risk management limits."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        # Analyze market
        strategy.analyze_market(df)

        # Check with low balance
        low_balance = Decimal("100")
        entry_data = strategy.check_entry_signal(df, low_balance)

        # Should not generate signal with insufficient balance
        # OR should generate very small position size
        if entry_data:
            signal, metrics, position_size = entry_data
            # Position size should be reasonable for balance
            assert position_size < low_balance * Decimal("0.5")


@pytest.mark.asyncio
class TestPositionManagementIntegration:
    """Test position management integration with strategy."""

    def test_open_position_creates_position(self, trend_follower_strategy, sample_ohlcv_data):
        """Test opening a position through the strategy."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        # Analyze market and get signal
        strategy.analyze_market(df)
        entry_data = strategy.check_entry_signal(df, Decimal("10000"))

        if entry_data:
            signal, metrics, position_size = entry_data

            # Open position
            position_id = strategy.open_position(signal, position_size)

            # Position should be created
            assert position_id is not None
            assert position_id in strategy.position_manager.active_positions

            # Position should have correct properties
            position = strategy.position_manager.active_positions[position_id]
            assert position.signal_type == signal.signal_type
            assert position.size == position_size
            assert position.entry_price == signal.entry_price

    def test_update_position_with_price_changes(self, trend_follower_strategy, sample_ohlcv_data):
        """Test updating position with price changes."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        # Create a position first
        strategy.analyze_market(df)
        entry_data = strategy.check_entry_signal(df, Decimal("10000"))

        if entry_data:
            signal, metrics, position_size = entry_data
            position_id = strategy.open_position(signal, position_size)

            # Get current price
            current_price = df["close"].iloc[-1]

            # Update position
            exit_reason = strategy.update_position(position_id, Decimal(str(current_price)), df)

            # May or may not trigger exit depending on price movement
            # But should not raise exception
            assert exit_reason is None or isinstance(exit_reason, str)

    def test_close_position_completes_trade(self, trend_follower_strategy, sample_ohlcv_data):
        """Test that closing position completes the trade cycle."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        # Create and close a position
        strategy.analyze_market(df)
        entry_data = strategy.check_entry_signal(df, Decimal("10000"))

        if entry_data:
            signal, metrics, position_size = entry_data
            position_id = strategy.open_position(signal, position_size)

            # Close position
            exit_price = signal.entry_price * Decimal("1.02")  # 2% profit
            strategy.close_position(position_id, "take_profit", exit_price)

            # Position should be removed from active positions
            assert position_id not in strategy.position_manager.active_positions

            # Trade should be recorded if logger is enabled
            if strategy.trade_logger:
                stats = strategy.trade_logger.get_statistics()
                assert stats["total_trades"] > 0


@pytest.mark.asyncio
class TestRiskManagementIntegration:
    """Test risk management integration."""

    def test_position_sizing_based_on_balance(self, trend_follower_strategy, sample_ohlcv_data):
        """Test that position sizing adapts to account balance."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        strategy.analyze_market(df)

        # Test with different balances
        balances = [Decimal("1000"), Decimal("5000"), Decimal("10000")]

        for balance in balances:
            entry_data = strategy.check_entry_signal(df, balance)
            if entry_data:
                signal, metrics, position_size = entry_data
                # Position size should scale with balance
                # and respect max position size
                assert position_size <= min(
                    balance * strategy.config.risk_per_trade_pct * 10,
                    strategy.config.max_position_size_usd,
                )

    def test_max_positions_limit_enforced(self, trend_follower_strategy, sample_ohlcv_data):
        """Test that maximum positions limit is enforced."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        # Try to open multiple positions
        max_positions = strategy.config.max_positions
        opened_positions = 0

        strategy.analyze_market(df)

        for _i in range(max_positions + 2):
            entry_data = strategy.check_entry_signal(df, Decimal("10000"))
            if entry_data:
                signal, metrics, position_size = entry_data
                # Manually set active positions to test limit
                strategy.risk_manager.active_positions = opened_positions
                if opened_positions < max_positions:
                    # Should allow opening
                    can_open = strategy.risk_manager.can_open_position(position_size)
                    if can_open:
                        opened_positions += 1
                else:
                    # Should not allow opening more than max
                    can_open = strategy.risk_manager.can_open_position(position_size)
                    assert not can_open


@pytest.mark.asyncio
class TestTradeLoggingIntegration:
    """Test trade logging and performance tracking."""

    def test_trade_logged_on_close(self, trend_follower_strategy, sample_ohlcv_data):
        """Test that trades are logged when positions close."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        if not strategy.trade_logger:
            pytest.skip("Trade logger not enabled")

        # Open and close a position
        strategy.analyze_market(df)
        entry_data = strategy.check_entry_signal(df, Decimal("10000"))

        if entry_data:
            signal, metrics, position_size = entry_data
            position_id = strategy.open_position(signal, position_size)

            # Close position
            exit_price = signal.entry_price * Decimal("1.03")
            strategy.close_position(position_id, "take_profit", exit_price)

            # Check statistics
            stats = strategy.trade_logger.get_statistics()
            assert stats["total_trades"] > 0
            assert "win_rate" in stats
            assert "profit_factor" in stats

    def test_performance_validation(self, trend_follower_strategy):
        """Test performance validation against issue #124 criteria."""
        strategy = trend_follower_strategy

        # Even without trades, should return validation structure
        validation = strategy.validate_performance()

        assert "validated" in validation
        assert "criteria" in validation or "reason" in validation


@pytest.mark.asyncio
class TestFullTradingCycle:
    """Test complete trading cycle integration."""

    def test_complete_trading_workflow(self, trend_follower_strategy, sample_ohlcv_data):
        """Test complete workflow: analyze → signal → open → update → close."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data
        balance = Decimal("10000")

        # Step 1: Analyze market
        conditions = strategy.analyze_market(df)
        assert conditions is not None

        # Step 2: Check for entry signal
        entry_data = strategy.check_entry_signal(df, balance)

        if entry_data:
            signal, metrics, position_size = entry_data

            # Step 3: Open position
            position_id = strategy.open_position(signal, position_size)
            assert position_id in strategy.position_manager.active_positions

            # Step 4: Update position (simulate price movement)
            for i in range(10):
                idx = -10 + i
                if idx < len(df):
                    current_price = Decimal(str(df["close"].iloc[idx]))
                    exit_reason = strategy.update_position(position_id, current_price, df)

                    if exit_reason:
                        # Position was closed by update
                        assert position_id not in strategy.position_manager.active_positions
                        break

            # Step 5: If still open, close manually
            if position_id in strategy.position_manager.active_positions:
                final_price = Decimal(str(df["close"].iloc[-1]))
                strategy.close_position(position_id, "manual_close", final_price)

            # Verify position is closed
            assert position_id not in strategy.position_manager.active_positions

    def test_multiple_positions_lifecycle(self, trend_follower_strategy, sample_ohlcv_data):
        """Test managing multiple positions simultaneously."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data
        balance = Decimal("10000")

        positions_opened = []

        # Try to open multiple positions (limited by max_positions)
        for _ in range(strategy.config.max_positions):
            strategy.analyze_market(df)
            entry_data = strategy.check_entry_signal(df, balance)

            if entry_data:
                signal, metrics, position_size = entry_data
                position_id = strategy.open_position(signal, position_size)
                positions_opened.append(position_id)

                # Adjust balance for next iteration
                balance -= position_size

        # Verify positions were opened
        assert len(positions_opened) <= strategy.config.max_positions

        # Close all positions
        final_price = Decimal(str(df["close"].iloc[-1]))
        for position_id in positions_opened:
            if position_id in strategy.position_manager.active_positions:
                strategy.close_position(position_id, "manual_close", final_price)

        # All should be closed
        for position_id in positions_opened:
            assert position_id not in strategy.position_manager.active_positions


@pytest.mark.asyncio
class TestStrategyStatistics:
    """Test strategy statistics and reporting."""

    def test_get_statistics_structure(self, trend_follower_strategy):
        """Test that statistics have correct structure."""
        strategy = trend_follower_strategy

        if strategy.trade_logger:
            stats = strategy.get_statistics()

            # Strategy returns nested structure
            assert "risk_metrics" in stats
            assert "active_positions" in stats
            assert "trade_statistics" in stats

            trade_stats = stats["trade_statistics"]
            assert "total_trades" in trade_stats
            assert "win_rate" in trade_stats
            assert "profit_factor" in trade_stats
            assert "max_drawdown" in trade_stats

    def test_statistics_update_after_trades(self, trend_follower_strategy, sample_ohlcv_data):
        """Test that statistics update after completing trades."""
        strategy = trend_follower_strategy
        df = sample_ohlcv_data

        if not strategy.trade_logger:
            pytest.skip("Trade logger not enabled")

        initial_stats = strategy.get_statistics()
        initial_trades = initial_stats["trade_statistics"]["total_trades"]

        # Complete a trade
        strategy.analyze_market(df)
        entry_data = strategy.check_entry_signal(df, Decimal("10000"))

        if entry_data:
            signal, metrics, position_size = entry_data
            position_id = strategy.open_position(signal, position_size)
            exit_price = signal.entry_price * Decimal("1.02")
            strategy.close_position(position_id, "take_profit", exit_price)

            # Statistics should update
            updated_stats = strategy.get_statistics()
            assert updated_stats["trade_statistics"]["total_trades"] == initial_trades + 1
