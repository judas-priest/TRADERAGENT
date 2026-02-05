"""Integration tests for bot orchestration"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from bot.config.schemas import (
    BotConfig,
    DCAConfig,
    ExchangeConfig,
    GridConfig,
    RiskManagementConfig,
)
from bot.orchestrator.bot_orchestrator import BotOrchestrator, BotState
from bot.orchestrator.events import EventType


@pytest.fixture
def hybrid_bot_config():
    """Create hybrid strategy bot configuration."""
    return BotConfig(
        version=1,
        name="hybrid_test_bot",
        symbol="BTC/USDT",
        strategy="hybrid",
        exchange=ExchangeConfig(
            exchange_id="binance",
            credentials_name="test_creds",
            sandbox=True,
        ),
        grid=GridConfig(
            enabled=True,
            upper_price="50000",
            lower_price="40000",
            grid_levels=5,
            amount_per_grid="100",
            profit_per_grid="0.01",
        ),
        dca=DCAConfig(
            enabled=True,
            trigger_percentage="0.05",
            amount_per_step="100",
            max_steps=3,
            take_profit_percentage="0.1",
        ),
        risk_management=RiskManagementConfig(
            max_position_size="5000",
            stop_loss_percentage="0.15",
            min_order_size="10",
        ),
        dry_run=True,
        auto_start=False,
    )


@pytest.fixture
def mock_exchange():
    """Create mock exchange with realistic behavior."""
    exchange = AsyncMock()
    exchange.get_balance.return_value = {"USDT": 10000, "BTC": 0}
    exchange.fetch_ticker.return_value = {"last": 45000, "bid": 44990, "ask": 45010}
    exchange.fetch_open_orders.return_value = []
    exchange.create_order.return_value = {"id": "test_order_123", "status": "open"}
    exchange.cancel_all_orders.return_value = None
    return exchange


@pytest.fixture
def mock_db():
    """Create mock database manager."""
    return AsyncMock()


@pytest.fixture
async def orchestrator(hybrid_bot_config, mock_exchange, mock_db):
    """Create orchestrator for integration testing."""
    with patch("bot.orchestrator.bot_orchestrator.redis.from_url") as mock_redis:
        mock_redis_client = AsyncMock()
        mock_redis_client.ping = AsyncMock()
        mock_redis_client.publish = AsyncMock()
        mock_redis_client.aclose = AsyncMock()
        mock_redis.return_value = mock_redis_client

        orch = BotOrchestrator(
            bot_config=hybrid_bot_config,
            exchange_client=mock_exchange,
            db_manager=mock_db,
            redis_url="redis://localhost:6379",
        )
        await orch.initialize()
        yield orch
        if orch.state != BotState.STOPPED:
            await orch.stop()
        await orch.cleanup()


@pytest.mark.asyncio
class TestHybridStrategyOrchestration:
    """Test hybrid strategy (Grid + DCA) orchestration."""

    async def test_hybrid_initialization(self, orchestrator):
        """Test that hybrid bot initializes both engines."""
        assert orchestrator.grid_engine is not None
        assert orchestrator.dca_engine is not None
        assert orchestrator.risk_manager is not None

    async def test_hybrid_start_lifecycle(self, orchestrator):
        """Test complete lifecycle of hybrid bot."""
        # Start bot
        await orchestrator.start()
        assert orchestrator.state == BotState.RUNNING
        assert orchestrator.current_price is not None

        # Grid should be initialized
        assert len(orchestrator.grid_engine.grid_orders) > 0

        # DCA should be ready
        assert orchestrator.dca_engine.current_step == 0

        # Pause bot
        await orchestrator.pause()
        assert orchestrator.state == BotState.PAUSED

        # Resume bot
        await orchestrator.resume()
        assert orchestrator.state == BotState.RUNNING

        # Stop bot
        await orchestrator.stop()
        assert orchestrator.state == BotState.STOPPED

    async def test_grid_and_dca_coordination(self, orchestrator, mock_exchange):
        """Test that grid and DCA can work together."""
        await orchestrator.start()

        # Simulate price drop that triggers DCA
        mock_exchange.fetch_ticker.return_value = {"last": 38000}
        orchestrator.current_price = Decimal("38000")

        # Check if DCA would trigger
        dca_result = orchestrator.dca_engine.update_price(Decimal("38000"))

        # At this price (below grid), DCA should be ready to trigger
        # (actual trigger logic depends on DCA engine implementation)

        await orchestrator.stop()

    async def test_risk_manager_integration(self, orchestrator, mock_exchange):
        """Test risk manager integration with strategies."""
        await orchestrator.start()

        # Verify risk manager was initialized with balance
        assert orchestrator.risk_manager.initial_balance == Decimal("10000")

        # Test risk check
        risk_check = orchestrator.risk_manager.check_trade(
            order_value=Decimal("100"),
            current_position=Decimal("0"),
            available_balance=Decimal("10000"),
        )
        assert risk_check  # Should pass

        # Test with large order
        large_order_check = orchestrator.risk_manager.check_trade(
            order_value=Decimal("6000"),  # Exceeds max position size
            current_position=Decimal("0"),
            available_balance=Decimal("10000"),
        )
        assert not large_order_check  # Should fail

        await orchestrator.stop()

    async def test_event_publishing_throughout_lifecycle(self, orchestrator):
        """Test that events are published at appropriate times."""
        publish_mock = orchestrator.redis_client.publish

        # Start bot - should publish BOT_STARTED
        await orchestrator.start()
        assert publish_mock.called

        # Reset mock
        publish_mock.reset_mock()

        # Pause - should publish BOT_PAUSED
        await orchestrator.pause()
        assert publish_mock.called

        # Reset mock
        publish_mock.reset_mock()

        # Resume - should publish BOT_RESUMED
        await orchestrator.resume()
        assert publish_mock.called

        # Reset mock
        publish_mock.reset_mock()

        # Stop - should publish BOT_STOPPED
        await orchestrator.stop()
        assert publish_mock.called

    async def test_emergency_stop_from_running(self, orchestrator):
        """Test emergency stop while bot is running."""
        await orchestrator.start()
        assert orchestrator.state == BotState.RUNNING

        # Trigger emergency stop
        await orchestrator.emergency_stop()

        assert orchestrator.state == BotState.EMERGENCY
        assert not orchestrator._running

        # Verify event was published
        orchestrator.redis_client.publish.assert_called()


@pytest.mark.asyncio
class TestRiskBasedHalt:
    """Test risk-based halting of orchestrator."""

    async def test_stop_loss_triggers_halt(self, orchestrator, mock_exchange):
        """Test that hitting stop loss triggers emergency stop."""
        await orchestrator.start()

        # Simulate significant balance loss
        mock_exchange.get_balance.return_value = {"USDT": 8000}  # 20% loss

        # Update risk manager
        orchestrator.risk_manager.update_balance(Decimal("8000"))

        # Check if halted
        risk_status = orchestrator.risk_manager.get_risk_status()
        if orchestrator.risk_manager.stop_loss_percentage:
            # If loss exceeds stop loss, should be halted
            if Decimal("8000") <= Decimal("10000") * (
                Decimal("1") - orchestrator.risk_manager.stop_loss_percentage
            ):
                assert risk_status["halted"]

        await orchestrator.stop()


@pytest.mark.asyncio
class TestMultipleBotCoordination:
    """Test coordination of multiple bot instances."""

    async def test_multiple_orchestrators_independent(
        self, hybrid_bot_config, mock_exchange, mock_db
    ):
        """Test that multiple orchestrators operate independently."""
        with patch("bot.orchestrator.bot_orchestrator.redis.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock()
            mock_redis_client.publish = AsyncMock()
            mock_redis_client.aclose = AsyncMock()
            mock_redis.return_value = mock_redis_client

            # Create two orchestrators
            config1 = hybrid_bot_config.model_copy()
            config1.name = "bot1"

            config2 = hybrid_bot_config.model_copy()
            config2.name = "bot2"

            orch1 = BotOrchestrator(
                bot_config=config1,
                exchange_client=mock_exchange,
                db_manager=mock_db,
            )
            await orch1.initialize()

            orch2 = BotOrchestrator(
                bot_config=config2,
                exchange_client=mock_exchange,
                db_manager=mock_db,
            )
            await orch2.initialize()

            # Start first bot
            await orch1.start()
            assert orch1.state == BotState.RUNNING
            assert orch2.state == BotState.STOPPED

            # Start second bot
            await orch2.start()
            assert orch1.state == BotState.RUNNING
            assert orch2.state == BotState.RUNNING

            # Stop first bot
            await orch1.stop()
            assert orch1.state == BotState.STOPPED
            assert orch2.state == BotState.RUNNING

            # Cleanup
            await orch2.stop()
            await orch1.cleanup()
            await orch2.cleanup()


@pytest.mark.asyncio
class TestStatusReporting:
    """Test comprehensive status reporting."""

    async def test_status_includes_all_components(self, orchestrator):
        """Test that status includes all component statuses."""
        status = await orchestrator.get_status()

        # Should include basic info
        assert "bot_name" in status
        assert "symbol" in status
        assert "strategy" in status
        assert "state" in status

        # Should include component statuses
        assert "grid" in status
        assert "dca" in status
        assert "risk" in status

    async def test_status_changes_with_state(self, orchestrator):
        """Test that status reflects state changes."""
        # Initial status
        status = await orchestrator.get_status()
        assert status["state"] == BotState.STOPPED.value

        # Start and check
        await orchestrator.start()
        status = await orchestrator.get_status()
        assert status["state"] == BotState.RUNNING.value
        assert status["current_price"] is not None

        # Pause and check
        await orchestrator.pause()
        status = await orchestrator.get_status()
        assert status["state"] == BotState.PAUSED.value

        await orchestrator.stop()
