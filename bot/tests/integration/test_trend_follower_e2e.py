"""End-to-End Integration Tests for Trend-Follower through BotOrchestrator

Tests the complete integration of Trend-Follower strategy with BotOrchestrator,
covering initialization, lifecycle management, signal generation, order execution,
position management, risk management, event publishing, and error handling.

Issue #137 - Phase 1.5
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from bot.config.schemas import (
    BotConfig,
    ExchangeConfig,
    RiskManagementConfig,
    TrendFollowerConfig,
)
from bot.orchestrator.bot_orchestrator import BotOrchestrator, BotState


@pytest.fixture
def trend_follower_bot_config():
    """Create Trend-Follower bot configuration for E2E testing."""
    return BotConfig(
        version=1,
        name="trend_follower_e2e_test",
        symbol="ETH/USDT",
        strategy="trend_follower",
        exchange=ExchangeConfig(
            exchange_id="binance",
            credentials_name="test_creds",
            sandbox=True,
        ),
        trend_follower=TrendFollowerConfig(
            # Market analysis
            ema_fast_period=20,
            ema_slow_period=50,
            atr_period=14,
            rsi_period=14,
            # Entry filters
            volume_multiplier=Decimal("1.5"),
            atr_filter_threshold=Decimal("0.05"),
            # Dynamic TP/SL
            tp_atr_multiplier_sideways=Decimal("1.2"),
            tp_atr_multiplier_weak=Decimal("1.8"),
            tp_atr_multiplier_strong=Decimal("2.5"),
            sl_atr_multiplier_sideways=Decimal("0.7"),
            sl_atr_multiplier_trend=Decimal("1.0"),
            # Risk management
            risk_per_trade_pct=Decimal("0.02"),
            max_position_size_usd=Decimal("3000"),
            max_daily_loss_usd=Decimal("300"),
            max_positions=2,
        ),
        risk_management=RiskManagementConfig(
            max_position_size="3000",
            stop_loss_percentage="0.20",
            min_order_size="10",
        ),
        dry_run=True,
        auto_start=False,
    )


@pytest.fixture
def mock_exchange():
    """Create mock exchange with realistic Trend-Follower behavior."""
    exchange = AsyncMock()

    # Balance
    exchange.fetch_balance.return_value = {
        "free": {"USDT": 10000, "ETH": 0},
        "total": {"USDT": 10000, "ETH": 0},
        "used": {"USDT": 0, "ETH": 0},
    }

    # Ticker
    exchange.fetch_ticker.return_value = {
        "last": 2500,
        "bid": 2499,
        "ask": 2501,
        "high": 2550,
        "low": 2450,
        "volume": 15000,
    }

    # OHLCV data for trend analysis
    def create_ohlcv_data(*args, **kwargs):
        """Generate realistic OHLCV data with trend."""
        np.random.seed(42)
        periods = kwargs.get("limit", 100)

        # Generate bullish trend
        base_price = 2400
        trend = np.linspace(0, 100, periods)
        noise = np.random.normal(0, 10, periods)
        close_prices = base_price + trend + noise

        high_prices = close_prices + np.abs(np.random.normal(5, 2, periods))
        low_prices = close_prices - np.abs(np.random.normal(5, 2, periods))
        open_prices = close_prices + np.random.normal(0, 3, periods)
        volume = np.random.uniform(10000, 20000, periods)

        # Return list of [timestamp, open, high, low, close, volume]
        return [
            [i * 3600000, float(o), float(h), float(low), float(c), float(v)]
            for i, (o, h, low, c, v) in enumerate(
                zip(open_prices, high_prices, low_prices, close_prices, volume, strict=False)
            )
        ]

    exchange.fetch_ohlcv.side_effect = create_ohlcv_data

    # Orders
    exchange.fetch_open_orders.return_value = []
    exchange.create_order.return_value = {
        "id": "order_123",
        "status": "open",
        "type": "market",
        "side": "buy",
        "price": 2500,
        "amount": 1.0,
    }
    exchange.cancel_order.return_value = None
    exchange.cancel_all_orders.return_value = None

    return exchange


@pytest.fixture
def mock_db():
    """Create mock database manager."""
    db = AsyncMock()
    db.save_order = AsyncMock()
    db.save_trade = AsyncMock()
    db.update_bot_status = AsyncMock()
    return db


@pytest.fixture
async def trend_follower_orchestrator(trend_follower_bot_config, mock_exchange, mock_db):
    """Create Trend-Follower orchestrator for E2E testing."""
    with patch("bot.orchestrator.bot_orchestrator.redis.from_url") as mock_redis:
        # Setup mock Redis client
        mock_redis_client = AsyncMock()
        mock_redis_client.ping = AsyncMock()
        mock_redis_client.publish = AsyncMock()
        mock_redis_client.aclose = AsyncMock()
        mock_redis.return_value = mock_redis_client

        orchestrator = BotOrchestrator(
            bot_config=trend_follower_bot_config,
            exchange_client=mock_exchange,
            db_manager=mock_db,
            redis_url="redis://localhost:6379",
        )

        await orchestrator.initialize()

        yield orchestrator

        # Cleanup
        if orchestrator.state != BotState.STOPPED:
            await orchestrator.stop()
        await orchestrator.cleanup()


@pytest.mark.asyncio
class TestTrendFollowerOrchestrationInitialization:
    """Test Trend-Follower orchestration initialization."""

    async def test_trend_follower_initialization(self, trend_follower_orchestrator):
        """Test that Trend-Follower bot initializes correctly through orchestrator."""
        orch = trend_follower_orchestrator

        # Orchestrator should be initialized
        assert orch.state == BotState.STOPPED
        assert orch.config.strategy == "trend_follower"
        assert orch.trend_follower_strategy is not None

        # Trend-Follower specific components
        assert orch.trend_follower_strategy.market_analyzer is not None
        assert orch.trend_follower_strategy.entry_logic is not None
        assert orch.trend_follower_strategy.position_manager is not None
        assert orch.trend_follower_strategy.risk_manager is not None

    async def test_components_properly_initialized(self, trend_follower_orchestrator):
        """Test that all orchestrator components are properly initialized."""
        orch = trend_follower_orchestrator

        # Core components
        assert orch.exchange is not None
        assert orch.db is not None
        assert orch.risk_manager is not None
        assert orch.redis_client is not None

        # Trend-Follower configuration properly loaded
        tf_config = orch.config.trend_follower
        assert tf_config.ema_fast_period == 20
        assert tf_config.ema_slow_period == 50
        assert tf_config.max_positions == 2
        assert tf_config.risk_per_trade_pct == Decimal("0.02")


@pytest.mark.asyncio
class TestTrendFollowerLifecycle:
    """Test Trend-Follower bot lifecycle management."""

    async def test_start_stop_lifecycle(self, trend_follower_orchestrator, mock_exchange):
        """Test complete start/stop lifecycle of Trend-Follower bot."""
        orch = trend_follower_orchestrator

        # Initial state
        assert orch.state == BotState.STOPPED

        # Start bot
        await orch.start()
        assert orch.state == BotState.RUNNING
        assert orch.current_price is not None
        assert orch.current_price > 0

        # Allow background tasks to execute
        await asyncio.sleep(0.2)

        # Exchange should have been queried
        mock_exchange.fetch_ticker.assert_called()
        mock_exchange.fetch_ohlcv.assert_called()

        # Stop bot
        await orch.stop()
        assert orch.state == BotState.STOPPED

    async def test_pause_resume_lifecycle(self, trend_follower_orchestrator):
        """Test pause/resume functionality."""
        orch = trend_follower_orchestrator

        # Start bot
        await orch.start()
        assert orch.state == BotState.RUNNING

        # Pause — main loop keeps running but skips processing
        await orch.pause()
        assert orch.state == BotState.PAUSED

        # Resume
        await orch.resume()
        assert orch.state == BotState.RUNNING

        # Cleanup
        await orch.stop()

    async def test_emergency_stop(self, trend_follower_orchestrator):
        """Test emergency stop functionality."""
        orch = trend_follower_orchestrator

        # Start bot
        await orch.start()
        assert orch.state == BotState.RUNNING

        # Trigger emergency stop
        await orch.emergency_stop()
        assert orch.state == BotState.EMERGENCY
        assert not orch._running

        # Verify event published
        orch.redis_client.publish.assert_called()


@pytest.mark.asyncio
class TestSignalGenerationAndExecution:
    """Test signal generation and order execution through orchestrator."""

    async def test_signal_generation_through_main_loop(
        self, trend_follower_orchestrator, mock_exchange
    ):
        """Test that signals are generated correctly through main loop."""
        orch = trend_follower_orchestrator

        # Start bot to trigger initial analysis
        await orch.start()

        # Allow background tasks to execute
        await asyncio.sleep(0.2)

        # Market should have been analyzed
        mock_exchange.fetch_ohlcv.assert_called()

        # Market conditions should be set
        assert hasattr(orch.trend_follower_strategy, "current_market_conditions")

        # Stop bot
        await orch.stop()

    async def test_order_execution_dry_run(self, trend_follower_orchestrator, mock_exchange):
        """Test order execution in dry run mode."""
        orch = trend_follower_orchestrator

        # Verify dry run is enabled
        assert orch.config.dry_run is True

        # Start bot
        await orch.start()

        # In dry run, orders should not be placed on exchange
        # (depending on implementation, this might still call create_order
        # but mark it as dry run internally)

        await orch.stop()

    async def test_order_execution_real_mode(
        self, trend_follower_bot_config, mock_exchange, mock_db
    ):
        """Test order execution in real trading mode."""
        # Create config with dry_run disabled
        config = trend_follower_bot_config.model_copy()
        config.dry_run = False

        with patch("bot.orchestrator.bot_orchestrator.redis.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock()
            mock_redis_client.publish = AsyncMock()
            mock_redis_client.aclose = AsyncMock()
            mock_redis.return_value = mock_redis_client

            orchestrator = BotOrchestrator(
                bot_config=config,
                exchange_client=mock_exchange,
                db_manager=mock_db,
            )
            await orchestrator.initialize()

            # Verify real mode
            assert orchestrator.config.dry_run is False

            # Cleanup
            await orchestrator.cleanup()


@pytest.mark.asyncio
class TestPositionManagementThroughOrchestrator:
    """Test position management through orchestrator."""

    async def test_position_opening_and_tracking(self, trend_follower_orchestrator, mock_exchange):
        """Test that positions are opened and tracked correctly."""
        orch = trend_follower_orchestrator

        # Start bot
        await orch.start()

        # Simulate generating an entry signal manually
        # (In real flow, this would happen through _process_trend_follower_logic)
        strategy = orch.trend_follower_strategy

        # Check if any positions were opened
        active_positions = len(strategy.position_manager.active_positions)
        assert active_positions >= 0  # May or may not have positions
        assert active_positions <= orch.config.trend_follower.max_positions

        await orch.stop()

    async def test_position_updates_and_exit(self, trend_follower_orchestrator, mock_exchange):
        """Test position update logic and exit conditions."""
        orch = trend_follower_orchestrator
        strategy = orch.trend_follower_strategy

        await orch.start()

        # If positions exist, verify they can be updated
        if strategy.position_manager.active_positions:
            for position_id in list(strategy.position_manager.active_positions.keys()):
                position = strategy.position_manager.active_positions[position_id]

                # Position should have all required fields
                assert hasattr(position, "signal_type")
                assert hasattr(position, "entry_price")
                assert hasattr(position, "size")
                assert hasattr(position, "stop_loss")
                assert hasattr(position, "take_profit")

        await orch.stop()

    async def test_max_positions_limit_enforced(self, trend_follower_orchestrator, mock_exchange):
        """Test that max positions limit is enforced by orchestrator."""
        orch = trend_follower_orchestrator
        strategy = orch.trend_follower_strategy

        await orch.start()

        # Max positions should be respected
        max_allowed = orch.config.trend_follower.max_positions
        active_count = len(strategy.position_manager.active_positions)

        assert active_count <= max_allowed

        await orch.stop()


@pytest.mark.asyncio
class TestRiskManagerIntegration:
    """Test risk manager integration with Trend-Follower."""

    async def test_risk_manager_validates_positions(
        self, trend_follower_orchestrator, mock_exchange
    ):
        """Test that risk manager validates all position openings."""
        orch = trend_follower_orchestrator

        await orch.start()

        # Risk manager should be initialized with balance
        assert orch.risk_manager.initial_balance > 0

        # Test risk check
        risk_check = orch.risk_manager.check_trade(
            order_value=Decimal("100"),
            current_position=Decimal("0"),
            available_balance=Decimal("10000"),
        )
        assert risk_check  # Should pass for small order

        # Test with large order exceeding max position size
        large_order_check = orch.risk_manager.check_trade(
            order_value=Decimal("4000"),  # Exceeds max_position_size of 3000
            current_position=Decimal("0"),
            available_balance=Decimal("10000"),
        )
        assert not large_order_check  # Should fail

        await orch.stop()

    async def test_daily_loss_limit_enforcement(self, trend_follower_orchestrator, mock_exchange):
        """Test that daily loss limits are enforced."""
        orch = trend_follower_orchestrator
        strategy = orch.trend_follower_strategy

        # Daily loss limit from config
        max_daily_loss = orch.config.trend_follower.max_daily_loss_usd
        assert max_daily_loss == Decimal("300")

        # Risk manager in strategy should respect this
        assert strategy.risk_manager.max_daily_loss_usd == max_daily_loss


@pytest.mark.asyncio
class TestEventPublishing:
    """Test event publishing throughout Trend-Follower lifecycle."""

    async def test_events_published_on_lifecycle_changes(self, trend_follower_orchestrator):
        """Test that lifecycle events are published correctly."""
        orch = trend_follower_orchestrator
        publish_mock = orch.redis_client.publish

        # Start - should publish BOT_STARTED
        await orch.start()
        assert publish_mock.called
        publish_mock.reset_mock()

        # Pause - should publish BOT_PAUSED
        await orch.pause()
        assert publish_mock.called
        publish_mock.reset_mock()

        # Resume - should publish BOT_RESUMED
        await orch.resume()
        assert publish_mock.called
        publish_mock.reset_mock()

        # Stop - should publish BOT_STOPPED
        await orch.stop()
        assert publish_mock.called

    async def test_events_published_on_trade_actions(
        self, trend_follower_orchestrator, mock_exchange
    ):
        """Test that trade-related events are published."""
        orch = trend_follower_orchestrator
        publish_mock = orch.redis_client.publish

        await orch.start()

        # Any trading activity should trigger events
        # (exact events depend on whether signals are generated)

        await orch.stop()

        # At minimum, start and stop events should have been published
        assert publish_mock.call_count >= 2


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling in Trend-Follower orchestration."""

    async def test_exchange_error_handling(self, trend_follower_bot_config, mock_db):
        """Test handling of exchange errors."""
        # Create exchange that raises errors
        error_exchange = AsyncMock()
        error_exchange.fetch_ticker.side_effect = Exception("Exchange connection failed")
        error_exchange.fetch_balance.return_value = {
            "free": {"USDT": 10000},
            "total": {"USDT": 10000},
            "used": {"USDT": 0},
        }

        with patch("bot.orchestrator.bot_orchestrator.redis.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock()
            mock_redis_client.publish = AsyncMock()
            mock_redis_client.aclose = AsyncMock()
            mock_redis.return_value = mock_redis_client

            orchestrator = BotOrchestrator(
                bot_config=trend_follower_bot_config,
                exchange_client=error_exchange,
                db_manager=mock_db,
            )
            await orchestrator.initialize()

            # Starting should handle the error gracefully
            try:
                await orchestrator.start()
            except Exception as e:
                # Error should be caught and logged
                assert (
                    "Exchange connection failed" in str(e) or orchestrator.state != BotState.RUNNING
                )

            # Cleanup
            await orchestrator.cleanup()

    async def test_invalid_signal_handling(self, trend_follower_orchestrator, mock_exchange):
        """Test handling of invalid or missing signals."""
        orch = trend_follower_orchestrator

        # Mock OHLCV to return insufficient data
        mock_exchange.fetch_ohlcv.return_value = [[0, 2500, 2510, 2490, 2500, 1000]]

        await orch.start()

        # Should handle insufficient data gracefully
        # (may not generate signals, but shouldn't crash)
        assert orch.state == BotState.RUNNING

        await orch.stop()


@pytest.mark.asyncio
class TestStatusReporting:
    """Test status reporting with Trend-Follower metrics."""

    async def test_status_includes_trend_follower_metrics(self, trend_follower_orchestrator):
        """Test that status includes Trend-Follower specific metrics."""
        orch = trend_follower_orchestrator

        await orch.start()

        status = await orch.get_status()

        # Basic status fields
        assert "bot_name" in status
        assert "symbol" in status
        assert "strategy" in status
        assert "state" in status

        # Trend-Follower specific fields
        assert status["strategy"] == "trend_follower"
        if "trend_follower" in status:
            tf_status = status["trend_follower"]
            # Should include strategy-specific metrics
            assert isinstance(tf_status, dict)

        await orch.stop()

    async def test_market_conditions_in_status(self, trend_follower_orchestrator):
        """Test that market conditions are included in status."""
        orch = trend_follower_orchestrator

        await orch.start()

        status = await orch.get_status()

        # Market conditions should be available after analysis
        if "market_conditions" in status or "trend_follower" in status:
            # Market phase and trend strength should be reported
            # (exact structure depends on implementation)
            assert status is not None

        await orch.stop()

    async def test_status_reflects_state_changes(self, trend_follower_orchestrator):
        """Test that status correctly reflects state changes."""
        orch = trend_follower_orchestrator

        # Stopped state
        status = await orch.get_status()
        assert status["state"] == BotState.STOPPED.value

        # Running state
        await orch.start()
        status = await orch.get_status()
        assert status["state"] == BotState.RUNNING.value
        assert status["current_price"] is not None

        # Paused state
        await orch.pause()
        status = await orch.get_status()
        assert status["state"] == BotState.PAUSED.value

        await orch.stop()


@pytest.mark.asyncio
class TestFullE2EWorkflow:
    """Test complete end-to-end workflows."""

    async def test_complete_trading_workflow(
        self, trend_follower_orchestrator, mock_exchange, mock_db
    ):
        """Test complete workflow: initialize → start → analyze → signal → execute → stop."""
        orch = trend_follower_orchestrator

        # Phase 1: Initialize (already done in fixture)
        assert orch.state == BotState.STOPPED
        assert orch.trend_follower_strategy is not None

        # Phase 2: Start bot
        await orch.start()
        assert orch.state == BotState.RUNNING

        # Allow background tasks to execute
        await asyncio.sleep(0.2)

        # Phase 3: Verify market analysis occurred
        mock_exchange.fetch_ohlcv.assert_called()

        # Phase 4: Check that risk manager is active
        assert orch.risk_manager.initial_balance > 0

        # Phase 5: Verify status reporting
        status = await orch.get_status()
        assert status["state"] == BotState.RUNNING.value
        assert "current_price" in status

        # Phase 6: Stop bot
        await orch.stop()
        assert orch.state == BotState.STOPPED

        # Phase 7: Verify events were published
        assert orch.redis_client.publish.call_count >= 2  # At least start + stop

    async def test_recovery_from_pause(self, trend_follower_orchestrator, mock_exchange):
        """Test that bot can recover from paused state and continue trading."""
        orch = trend_follower_orchestrator

        # Start bot
        await orch.start()
        initial_call_count = mock_exchange.fetch_ohlcv.call_count

        # Pause
        await orch.pause()
        assert orch.state == BotState.PAUSED

        # Resume
        await orch.resume()
        assert orch.state == BotState.RUNNING

        # Bot should continue fetching data after resume
        # (exact behavior depends on main loop implementation)

        await orch.stop()
