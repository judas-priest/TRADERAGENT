"""
Database load testing — concurrent writes/reads under load.

Uses in-memory SQLite. Note: SQLite does not test PostgreSQL connection pool
behavior, but validates application code paths (session creation, commit,
rollback) under concurrent load.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Bot, ExchangeCredential, Order, Trade


class TestDatabaseUnderLoad:
    """Test database operations under concurrent load."""

    async def test_50_concurrent_order_writes(self, db_session_factory, seed_bot):
        """50 concurrent tasks each writing an Order."""
        _, bot_id = seed_bot

        async def write_order(i: int):
            async with db_session_factory() as session:
                order = Order(
                    bot_id=bot_id,
                    exchange_order_id=f"LOAD-{i:04d}",
                    symbol="BTCUSDT",
                    order_type="limit",
                    side="buy" if i % 2 == 0 else "sell",
                    price=Decimal("45000") + i,
                    amount=Decimal("0.001"),
                    status="open",
                )
                session.add(order)
                await session.commit()

        start = time.perf_counter()
        await asyncio.gather(*[write_order(i) for i in range(50)])
        elapsed = time.perf_counter() - start

        # Verify all persisted
        async with db_session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(Order).where(Order.bot_id == bot_id)
            )
            count = result.scalar()

        assert count == 50, f"Expected 50 orders, got {count}"
        assert elapsed < 5.0, f"50 concurrent writes took {elapsed:.2f}s"
        print(f"\n  50 concurrent order writes: {elapsed:.2f}s ({50/elapsed:.0f} writes/s)")

    async def test_500_sequential_writes_throughput(self, db_session_factory, seed_bot):
        """500 sequential Order writes — measure throughput."""
        _, bot_id = seed_bot

        start = time.perf_counter()
        async with db_session_factory() as session:
            for i in range(500):
                order = Order(
                    bot_id=bot_id,
                    exchange_order_id=f"SEQ-{i:04d}",
                    symbol="BTCUSDT",
                    order_type="limit",
                    side="buy",
                    price=Decimal("45000") + i,
                    amount=Decimal("0.001"),
                    status="open",
                )
                session.add(order)
            await session.commit()
        elapsed = time.perf_counter() - start

        throughput = 500 / elapsed
        assert throughput > 100, f"Throughput: {throughput:.0f} writes/s (need >100)"
        print(f"\n  500 sequential writes: {elapsed:.2f}s ({throughput:.0f} writes/s)")

    async def test_mixed_read_write_100(self, db_session_factory, seed_bot):
        """50 write tasks + 50 read tasks running concurrently."""
        _, bot_id = seed_bot

        # Pre-seed some data
        async with db_session_factory() as session:
            for i in range(10):
                session.add(Order(
                    bot_id=bot_id,
                    exchange_order_id=f"PRE-{i:04d}",
                    symbol="BTCUSDT",
                    order_type="limit",
                    side="buy",
                    price=Decimal("45000"),
                    amount=Decimal("0.001"),
                    status="open",
                ))
            await session.commit()

        async def write_task(i: int):
            async with db_session_factory() as session:
                session.add(Order(
                    bot_id=bot_id,
                    exchange_order_id=f"MIX-W-{i:04d}",
                    symbol="BTCUSDT",
                    order_type="limit",
                    side="sell",
                    price=Decimal("46000"),
                    amount=Decimal("0.001"),
                    status="open",
                ))
                await session.commit()

        async def read_task():
            async with db_session_factory() as session:
                result = await session.execute(
                    select(Order).where(Order.bot_id == bot_id).limit(10)
                )
                return result.scalars().all()

        start = time.perf_counter()
        write_results = asyncio.gather(*[write_task(i) for i in range(50)])
        read_results = asyncio.gather(*[read_task() for _ in range(50)])
        await asyncio.gather(write_results, read_results)
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0, f"Mixed read/write took {elapsed:.2f}s"
        print(f"\n  50 write + 50 read concurrent: {elapsed:.2f}s")

    async def test_bulk_orders_and_trades_200(self, db_session_factory, seed_bot):
        """100 Orders + 100 Trades written concurrently."""
        _, bot_id = seed_bot

        async def write_order(i: int):
            async with db_session_factory() as session:
                session.add(Order(
                    bot_id=bot_id,
                    exchange_order_id=f"BULK-O-{i:04d}",
                    symbol="BTCUSDT",
                    order_type="limit",
                    side="buy",
                    price=Decimal("45000"),
                    amount=Decimal("0.001"),
                    status="filled",
                ))
                await session.commit()

        async def write_trade(i: int):
            async with db_session_factory() as session:
                session.add(Trade(
                    bot_id=bot_id,
                    exchange_trade_id=f"BULK-T-{i:04d}",
                    exchange_order_id=f"BULK-O-{i:04d}",
                    symbol="BTCUSDT",
                    side="buy",
                    price=Decimal("45000"),
                    amount=Decimal("0.001"),
                    fee=Decimal("0.045"),
                    fee_currency="USDT",
                    executed_at=datetime.now(timezone.utc),
                ))
                await session.commit()

        start = time.perf_counter()
        await asyncio.gather(
            *[write_order(i) for i in range(100)],
            *[write_trade(i) for i in range(100)],
        )
        elapsed = time.perf_counter() - start

        # Verify counts
        async with db_session_factory() as session:
            order_count = (await session.execute(
                select(func.count()).select_from(Order).where(Order.bot_id == bot_id)
            )).scalar()
            trade_count = (await session.execute(
                select(func.count()).select_from(Trade).where(Trade.bot_id == bot_id)
            )).scalar()

        assert order_count == 100, f"Expected 100 orders, got {order_count}"
        assert trade_count == 100, f"Expected 100 trades, got {trade_count}"
        assert elapsed < 10.0, f"200 bulk writes took {elapsed:.2f}s"
        print(f"\n  100 orders + 100 trades: {elapsed:.2f}s ({200/elapsed:.0f} writes/s)")

    async def test_concurrent_bot_queries_50(self, db_session_factory, seed_bot):
        """50 concurrent bot lookups by name."""
        _, _ = seed_bot

        async def query_bot():
            async with db_session_factory() as session:
                result = await session.execute(
                    select(Bot).where(Bot.name == "load-bot")
                )
                bot = result.scalar_one_or_none()
                assert bot is not None
                return bot

        start = time.perf_counter()
        results = await asyncio.gather(*[query_bot() for _ in range(50)])
        elapsed = time.perf_counter() - start

        assert len(results) == 50
        assert all(r.name == "load-bot" for r in results)
        assert elapsed < 3.0, f"50 bot queries took {elapsed:.2f}s"
        print(f"\n  50 concurrent bot queries: {elapsed:.2f}s ({50/elapsed:.0f} queries/s)")
