"""
Integration tests — Database persistence during trading workflows.

Uses SQLite in-memory for testing. Validates CRUD operations, transaction
integrity, and model relationships in the context of trading activity.
"""

import json
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import BigInteger, Integer, event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import (
    Base,
    Bot,
    BotLog,
    DCAHistory,
    ExchangeCredential,
    GridLevel,
    Order,
    Trade,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _map_bigint_to_int(metadata):
    """Replace BigInteger columns with Integer for SQLite compatibility."""
    for table in metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, BigInteger):
                column.type = Integer()


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite async engine."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        # Map BigInteger -> Integer for SQLite autoincrement compatibility
        _map_bigint_to_int(Base.metadata)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    """Create session factory from engine."""
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def session(session_factory):
    """Create a single session for a test."""
    async with session_factory() as sess:
        yield sess


async def _create_credential(session: AsyncSession) -> ExchangeCredential:
    """Helper to create a test ExchangeCredential."""
    cred = ExchangeCredential(
        name="test-bybit",
        exchange_id="bybit",
        api_key_encrypted="enc_key_123",
        api_secret_encrypted="enc_secret_456",
        is_sandbox=True,
        is_active=True,
    )
    session.add(cred)
    await session.flush()
    await session.refresh(cred)
    return cred


async def _create_bot(
    session: AsyncSession,
    cred: ExchangeCredential,
    name: str = "test-bot",
    strategy: str = "grid",
) -> Bot:
    """Helper to create a test Bot."""
    bot = Bot(
        name=name,
        credentials_id=cred.id,
        symbol="BTCUSDT",
        strategy=strategy,
        status="stopped",
        config_data=json.dumps({"version": 1}),
    )
    session.add(bot)
    await session.flush()
    await session.refresh(bot)
    return bot


# ===========================================================================
# Credential CRUD
# ===========================================================================


class TestCredentialCRUD:
    async def test_create_credential(self, session):
        cred = await _create_credential(session)
        assert cred.id is not None
        assert cred.name == "test-bybit"
        assert cred.exchange_id == "bybit"

    async def test_read_credential(self, session):
        cred = await _create_credential(session)
        result = await session.execute(
            select(ExchangeCredential).where(ExchangeCredential.id == cred.id)
        )
        fetched = result.scalar_one()
        assert fetched.name == "test-bybit"

    async def test_update_credential(self, session):
        cred = await _create_credential(session)
        cred.is_active = False
        await session.flush()
        result = await session.execute(
            select(ExchangeCredential).where(ExchangeCredential.id == cred.id)
        )
        fetched = result.scalar_one()
        assert fetched.is_active is False

    async def test_unique_name_constraint(self, session):
        await _create_credential(session)
        cred2 = ExchangeCredential(
            name="test-bybit",  # Duplicate
            exchange_id="bybit",
            api_key_encrypted="x",
            api_secret_encrypted="y",
        )
        session.add(cred2)
        with pytest.raises(Exception):  # IntegrityError
            await session.flush()


# ===========================================================================
# Bot CRUD
# ===========================================================================


class TestBotCRUD:
    async def test_create_bot(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        assert bot.id is not None
        assert bot.symbol == "BTCUSDT"
        assert bot.strategy == "grid"

    async def test_bot_initial_values(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        assert bot.total_invested == Decimal("0")
        assert bot.current_profit == Decimal("0")
        assert bot.total_trades == 0
        assert bot.status == "stopped"

    async def test_bot_credential_relationship(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        assert bot.credentials_id == cred.id

    async def test_update_bot_status(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        bot.status = "running"
        bot.started_at = datetime.utcnow()
        await session.flush()

        result = await session.execute(select(Bot).where(Bot.id == bot.id))
        fetched = result.scalar_one()
        assert fetched.status == "running"
        assert fetched.started_at is not None

    async def test_bot_strategy_types(self, session):
        cred = await _create_credential(session)
        for strategy in ["grid", "dca", "hybrid"]:
            bot = await _create_bot(session, cred, name=f"bot-{strategy}", strategy=strategy)
            assert bot.strategy == strategy


# ===========================================================================
# Order CRUD
# ===========================================================================


class TestOrderCRUD:
    async def test_create_order(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        order = Order(
            bot_id=bot.id,
            exchange_order_id="ORD-001",
            symbol="BTCUSDT",
            order_type="limit",
            side="buy",
            price=Decimal("45000"),
            amount=Decimal("0.001"),
            status="open",
        )
        session.add(order)
        await session.flush()
        await session.refresh(order)
        assert order.id is not None
        assert order.filled == Decimal("0")

    async def test_order_fill(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        order = Order(
            bot_id=bot.id,
            exchange_order_id="ORD-002",
            symbol="BTCUSDT",
            order_type="limit",
            side="buy",
            price=Decimal("45000"),
            amount=Decimal("0.001"),
            status="open",
        )
        session.add(order)
        await session.flush()

        # Fill the order
        order.filled = order.amount
        order.status = "closed"
        order.filled_at = datetime.utcnow()
        await session.flush()

        result = await session.execute(select(Order).where(Order.id == order.id))
        fetched = result.scalar_one()
        assert fetched.status == "closed"
        assert fetched.filled == Decimal("0.001")

    async def test_multiple_orders_per_bot(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)

        for i in range(5):
            order = Order(
                bot_id=bot.id,
                exchange_order_id=f"ORD-{i:03d}",
                symbol="BTCUSDT",
                order_type="limit",
                side="buy" if i % 2 == 0 else "sell",
                price=Decimal("45000") + i * 100,
                amount=Decimal("0.001"),
                status="open",
            )
            session.add(order)

        await session.flush()

        result = await session.execute(
            select(Order).where(Order.bot_id == bot.id)
        )
        orders = result.scalars().all()
        assert len(orders) == 5

    async def test_grid_level_order(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        order = Order(
            bot_id=bot.id,
            exchange_order_id="ORD-GRID-001",
            symbol="BTCUSDT",
            order_type="limit",
            side="buy",
            price=Decimal("44500"),
            amount=Decimal("0.001"),
            grid_level=3,
            status="open",
        )
        session.add(order)
        await session.flush()
        await session.refresh(order)
        assert order.grid_level == 3


# ===========================================================================
# Trade CRUD
# ===========================================================================


class TestTradeCRUD:
    async def test_create_trade(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        trade = Trade(
            bot_id=bot.id,
            exchange_trade_id="TRD-001",
            exchange_order_id="ORD-001",
            symbol="BTCUSDT",
            side="buy",
            price=Decimal("45000"),
            amount=Decimal("0.001"),
            fee=Decimal("0.00001"),
            fee_currency="BTC",
            profit=Decimal("5.50"),
            executed_at=datetime.utcnow(),
        )
        session.add(trade)
        await session.flush()
        await session.refresh(trade)
        assert trade.id is not None
        assert trade.profit == Decimal("5.50")

    async def test_trade_pnl_tracking(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)

        # Winning trade
        trade1 = Trade(
            bot_id=bot.id,
            exchange_trade_id="TRD-W01",
            exchange_order_id="ORD-W01",
            symbol="BTCUSDT",
            side="sell",
            price=Decimal("46000"),
            amount=Decimal("0.001"),
            fee=Decimal("0.00001"),
            fee_currency="BTC",
            profit=Decimal("10.00"),
            executed_at=datetime.utcnow(),
        )
        # Losing trade
        trade2 = Trade(
            bot_id=bot.id,
            exchange_trade_id="TRD-L01",
            exchange_order_id="ORD-L01",
            symbol="BTCUSDT",
            side="sell",
            price=Decimal("44000"),
            amount=Decimal("0.001"),
            fee=Decimal("0.00001"),
            fee_currency="BTC",
            profit=Decimal("-5.00"),
            executed_at=datetime.utcnow(),
        )
        session.add_all([trade1, trade2])
        await session.flush()

        result = await session.execute(
            select(Trade).where(Trade.bot_id == bot.id)
        )
        trades = result.scalars().all()
        total_pnl = sum(t.profit for t in trades if t.profit)
        assert total_pnl == Decimal("5.00")


# ===========================================================================
# Grid Level CRUD
# ===========================================================================


class TestGridLevelCRUD:
    async def test_create_grid_levels(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)

        for i in range(5):
            level = GridLevel(
                bot_id=bot.id,
                level=i + 1,
                price=Decimal("44000") + i * Decimal("500"),
                is_active=True,
            )
            session.add(level)

        await session.flush()
        result = await session.execute(
            select(GridLevel).where(GridLevel.bot_id == bot.id)
        )
        levels = result.scalars().all()
        assert len(levels) == 5

    async def test_deactivate_grid_level(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        level = GridLevel(
            bot_id=bot.id, level=1, price=Decimal("44500"), is_active=True
        )
        session.add(level)
        await session.flush()

        level.is_active = False
        level.sell_order_id = "SELL-001"
        await session.flush()

        result = await session.execute(
            select(GridLevel).where(GridLevel.id == level.id)
        )
        fetched = result.scalar_one()
        assert fetched.is_active is False
        assert fetched.sell_order_id == "SELL-001"


# ===========================================================================
# Trading Workflow Integration
# ===========================================================================


class TestTradingWorkflow:
    """Test complete trading workflows using the database models."""

    async def test_full_grid_trade_lifecycle(self, session):
        """Simulate: create bot → place grid orders → fill → record trades."""
        # 1. Create credentials and bot
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred, strategy="grid")
        bot.status = "running"

        # 2. Create grid levels
        prices = [Decimal("44000"), Decimal("44500"), Decimal("45000")]
        for i, price in enumerate(prices):
            level = GridLevel(
                bot_id=bot.id, level=i + 1, price=price, is_active=True
            )
            session.add(level)

        # 3. Place buy orders at grid levels
        for i, price in enumerate(prices):
            order = Order(
                bot_id=bot.id,
                exchange_order_id=f"BUY-{i+1}",
                symbol="BTCUSDT",
                order_type="limit",
                side="buy",
                price=price,
                amount=Decimal("0.001"),
                grid_level=i + 1,
                status="open",
            )
            session.add(order)

        await session.flush()

        # 4. Simulate: price drops, buy order at 44500 fills
        result = await session.execute(
            select(Order).where(Order.exchange_order_id == "BUY-2")
        )
        filled_order = result.scalar_one()
        filled_order.status = "closed"
        filled_order.filled = filled_order.amount
        filled_order.filled_at = datetime.utcnow()

        # 5. Record trade
        trade = Trade(
            bot_id=bot.id,
            exchange_trade_id="TRD-GRID-1",
            exchange_order_id="BUY-2",
            symbol="BTCUSDT",
            side="buy",
            price=Decimal("44500"),
            amount=Decimal("0.001"),
            fee=Decimal("0.00000045"),
            fee_currency="BTC",
            executed_at=datetime.utcnow(),
        )
        session.add(trade)
        bot.total_trades += 1
        await session.flush()

        # Verify
        assert bot.total_trades == 1
        result = await session.execute(
            select(Trade).where(Trade.bot_id == bot.id)
        )
        trades = result.scalars().all()
        assert len(trades) == 1
        assert trades[0].price == Decimal("44500")

    async def test_bot_profit_tracking(self, session):
        """Track cumulative profit across multiple trades."""
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        bot.status = "running"

        profits = [Decimal("10"), Decimal("-3"), Decimal("7"), Decimal("5")]
        for i, profit in enumerate(profits):
            trade = Trade(
                bot_id=bot.id,
                exchange_trade_id=f"TRD-{i}",
                exchange_order_id=f"ORD-{i}",
                symbol="BTCUSDT",
                side="sell",
                price=Decimal("45000"),
                amount=Decimal("0.001"),
                fee=Decimal("0.00001"),
                fee_currency="BTC",
                profit=profit,
                executed_at=datetime.utcnow(),
            )
            session.add(trade)
            bot.current_profit += profit
            bot.total_trades += 1

        await session.flush()

        assert bot.total_trades == 4
        assert bot.current_profit == Decimal("19")

    async def test_bot_stop_workflow(self, session):
        """Simulate stopping a bot: cancel open orders, update status."""
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        bot.status = "running"

        # Place some open orders
        for i in range(3):
            order = Order(
                bot_id=bot.id,
                exchange_order_id=f"ORD-STOP-{i}",
                symbol="BTCUSDT",
                order_type="limit",
                side="buy",
                price=Decimal("44000") + i * 500,
                amount=Decimal("0.001"),
                status="open",
            )
            session.add(order)
        await session.flush()

        # Cancel all open orders
        result = await session.execute(
            select(Order).where(Order.bot_id == bot.id, Order.status == "open")
        )
        open_orders = result.scalars().all()
        for order in open_orders:
            order.status = "canceled"

        bot.status = "stopped"
        bot.stopped_at = datetime.utcnow()
        await session.flush()

        # Verify all orders cancelled
        result = await session.execute(
            select(Order).where(Order.bot_id == bot.id, Order.status == "open")
        )
        remaining = result.scalars().all()
        assert len(remaining) == 0
        assert bot.status == "stopped"

    async def test_multi_bot_isolation(self, session):
        """Multiple bots should have isolated data."""
        cred = await _create_credential(session)
        bot1 = await _create_bot(session, cred, name="bot-1", strategy="grid")
        bot2 = await _create_bot(session, cred, name="bot-2", strategy="dca")

        # Add trades to bot1
        trade1 = Trade(
            bot_id=bot1.id,
            exchange_trade_id="TRD-B1-1",
            exchange_order_id="ORD-B1-1",
            symbol="BTCUSDT",
            side="buy",
            price=Decimal("45000"),
            amount=Decimal("0.001"),
            fee=Decimal("0"),
            fee_currency="USDT",
            executed_at=datetime.utcnow(),
        )
        session.add(trade1)
        bot1.total_trades = 1
        await session.flush()

        # Bot2 should still have 0 trades
        result = await session.execute(
            select(Trade).where(Trade.bot_id == bot2.id)
        )
        bot2_trades = result.scalars().all()
        assert len(bot2_trades) == 0
        assert bot2.total_trades == 0


# ===========================================================================
# Bot Log
# ===========================================================================


class TestBotLog:
    async def test_create_log_entry(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)
        log = BotLog(
            bot_id=bot.id,
            level="INFO",
            message="Bot started successfully",
        )
        session.add(log)
        await session.flush()
        await session.refresh(log)
        assert log.id is not None
        assert log.level == "INFO"

    async def test_multiple_log_entries(self, session):
        cred = await _create_credential(session)
        bot = await _create_bot(session, cred)

        messages = ["Starting bot", "Analyzing market", "Order placed", "Trade executed"]
        for msg in messages:
            log = BotLog(bot_id=bot.id, level="INFO", message=msg)
            session.add(log)
        await session.flush()

        result = await session.execute(
            select(BotLog).where(BotLog.bot_id == bot.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 4
