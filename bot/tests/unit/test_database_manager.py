"""Tests for DatabaseManager"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import (
    Bot,
    DatabaseManager,
    ExchangeCredential,
    GridLevel,
    Order,
)


@pytest.mark.asyncio
class TestDatabaseManager:
    """Test DatabaseManager functionality"""

    async def test_create_bot(self, db_session: AsyncSession):
        """Test creating a bot"""
        credential = ExchangeCredential(
            name="test_creds",
            exchange_id="binance",
            api_key_encrypted="encrypted_key",
            api_secret_encrypted="encrypted_secret",
        )
        db_session.add(credential)
        await db_session.flush()

        bot = Bot(
            name="test_bot",
            credentials_id=credential.id,
            symbol="BTC/USDT",
            strategy="grid",
            config_data="{}",
        )
        db_session.add(bot)
        await db_session.commit()

        assert bot.id is not None
        assert bot.name == "test_bot"

    async def test_get_bot(self, db_session: AsyncSession):
        """Test getting a bot by ID"""
        credential = ExchangeCredential(
            name="test_creds",
            exchange_id="binance",
            api_key_encrypted="encrypted_key",
            api_secret_encrypted="encrypted_secret",
        )
        db_session.add(credential)
        await db_session.flush()

        bot = Bot(
            name="test_bot",
            credentials_id=credential.id,
            symbol="BTC/USDT",
            strategy="grid",
            config_data="{}",
        )
        db_session.add(bot)
        await db_session.commit()

        # Retrieve
        from sqlalchemy import select

        result = await db_session.execute(select(Bot).where(Bot.id == bot.id))
        retrieved_bot = result.scalar_one()

        assert retrieved_bot.id == bot.id
        assert retrieved_bot.name == "test_bot"

    async def test_create_order(self, db_session: AsyncSession):
        """Test creating an order"""
        credential = ExchangeCredential(
            name="test_creds",
            exchange_id="binance",
            api_key_encrypted="encrypted_key",
            api_secret_encrypted="encrypted_secret",
        )
        db_session.add(credential)
        await db_session.flush()

        bot = Bot(
            name="test_bot",
            credentials_id=credential.id,
            symbol="BTC/USDT",
            strategy="grid",
            config_data="{}",
        )
        db_session.add(bot)
        await db_session.flush()

        order = Order(
            bot_id=bot.id,
            exchange_order_id="12345",
            symbol="BTC/USDT",
            order_type="limit",
            side="buy",
            price=Decimal("45000"),
            amount=Decimal("0.001"),
        )
        db_session.add(order)
        await db_session.commit()

        assert order.id is not None
        assert order.exchange_order_id == "12345"

    async def test_grid_level(self, db_session: AsyncSession):
        """Test creating grid levels"""
        credential = ExchangeCredential(
            name="test_creds",
            exchange_id="binance",
            api_key_encrypted="encrypted_key",
            api_secret_encrypted="encrypted_secret",
        )
        db_session.add(credential)
        await db_session.flush()

        bot = Bot(
            name="test_bot",
            credentials_id=credential.id,
            symbol="BTC/USDT",
            strategy="grid",
            config_data="{}",
        )
        db_session.add(bot)
        await db_session.flush()

        grid_level = GridLevel(
            bot_id=bot.id,
            level=1,
            price=Decimal("45000"),
        )
        db_session.add(grid_level)
        await db_session.commit()

        assert grid_level.id is not None
        assert grid_level.level == 1

    async def test_bot_relationships(self, db_session: AsyncSession):
        """Test bot relationships"""
        credential = ExchangeCredential(
            name="test_creds",
            exchange_id="binance",
            api_key_encrypted="encrypted_key",
            api_secret_encrypted="encrypted_secret",
        )
        db_session.add(credential)
        await db_session.flush()

        bot = Bot(
            name="test_bot",
            credentials_id=credential.id,
            symbol="BTC/USDT",
            strategy="grid",
            config_data="{}",
        )
        db_session.add(bot)
        await db_session.flush()

        # Add orders
        order1 = Order(
            bot_id=bot.id,
            exchange_order_id="order1",
            symbol="BTC/USDT",
            order_type="limit",
            side="buy",
            price=Decimal("45000"),
            amount=Decimal("0.001"),
        )
        order2 = Order(
            bot_id=bot.id,
            exchange_order_id="order2",
            symbol="BTC/USDT",
            order_type="limit",
            side="sell",
            price=Decimal("46000"),
            amount=Decimal("0.001"),
        )
        db_session.add_all([order1, order2])
        await db_session.commit()

        # Refresh to load relationships
        await db_session.refresh(bot, ["orders"])

        assert len(bot.orders) == 2
