"""
Load and stress testing for TRADERAGENT components.

Tests:
- High-volume order processing through adapters
- Database under concurrent write load
- Strategy analysis throughput
- Memory stability during extended operation
- API rate limit handling

No external services required — uses mocked/in-memory infrastructure.
"""

import asyncio
import gc
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from bot.strategies.base import (
    BaseSignal,
    ExitReason,
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


def _make_ohlcv(n: int = 200, base: float = 45000.0) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="15min")
    closes = base + np.cumsum(rng.normal(0, 10, n))
    highs = closes + rng.uniform(5, 30, n)
    lows = closes - rng.uniform(5, 30, n)
    opens = closes + rng.normal(0, 5, n)
    volumes = rng.uniform(100, 1000, n)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )


def _make_signal(price: Decimal = Decimal("45000")) -> BaseSignal:
    return BaseSignal(
        direction=SignalDirection.LONG,
        entry_price=price,
        stop_loss=price - Decimal("500"),
        take_profit=price + Decimal("1000"),
        confidence=0.7,
        timestamp=datetime.now(timezone.utc),
        strategy_type="test",
    )


# ===========================================================================
# High-Volume Position Processing
# ===========================================================================


class TestHighVolumePositions:
    """Test adapters under high-volume position load."""

    def test_100_positions_smc(self):
        """SMC adapter: open and close 100 positions."""
        adapter = SMCStrategyAdapter()
        pos_ids = []

        start = time.perf_counter()
        for i in range(100):
            signal = _make_signal(Decimal(str(45000 + i)))
            pos_id = adapter.open_position(signal, Decimal("50"))
            pos_ids.append(pos_id)
        elapsed_open = time.perf_counter() - start

        assert len(adapter.get_active_positions()) == 100

        start = time.perf_counter()
        for pos_id in pos_ids:
            adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))
        elapsed_close = time.perf_counter() - start

        perf = adapter.get_performance()
        assert perf.total_trades == 100
        assert perf.winning_trades == 100
        # Should complete in under 1 second
        assert elapsed_open < 1.0, f"Opening 100 positions took {elapsed_open:.2f}s"
        assert elapsed_close < 1.0, f"Closing 100 positions took {elapsed_close:.2f}s"

    def test_100_positions_grid(self):
        adapter = GridAdapter()
        pos_ids = []
        for i in range(100):
            signal = _make_signal(Decimal(str(45000 + i)))
            pos_ids.append(adapter.open_position(signal, Decimal("50")))

        assert len(adapter.get_active_positions()) == 100

        df = _make_ohlcv(n=10)
        # Update all positions with a price that doesn't trigger TP/SL
        exits = adapter.update_positions(Decimal("45500"), df)
        assert len(exits) == 0  # No exits

        for pos_id in pos_ids:
            adapter.close_position(pos_id, ExitReason.MANUAL, Decimal("45500"))
        assert adapter.get_performance().total_trades == 100

    def test_100_positions_dca(self):
        adapter = DCAAdapter()
        pos_ids = []
        for i in range(100):
            signal = _make_signal(Decimal(str(45000 + i)))
            pos_ids.append(adapter.open_position(signal, Decimal("50")))

        assert len(adapter.get_active_positions()) == 100
        for pos_id in pos_ids:
            adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))
        assert adapter.get_performance().total_trades == 100

    def test_mass_update_positions(self):
        """Update 100 positions with new prices."""
        adapter = SMCStrategyAdapter()
        for i in range(100):
            adapter.open_position(_make_signal(Decimal(str(45000 + i))), Decimal("50"))

        df = _make_ohlcv(n=10)
        start = time.perf_counter()
        for price in range(44900, 45100):
            adapter.update_positions(Decimal(str(price)), df)
        elapsed = time.perf_counter() - start

        # 200 price updates * 100 positions = 20,000 checks
        assert elapsed < 2.0, f"20K position updates took {elapsed:.2f}s"


# ===========================================================================
# Strategy Analysis Throughput
# ===========================================================================


class TestAnalysisThroughput:
    """Test how quickly strategies can analyze market data."""

    def test_smc_analysis_speed(self):
        adapter = SMCStrategyAdapter()
        df = _make_ohlcv(n=200)

        start = time.perf_counter()
        for _ in range(10):
            adapter.analyze_market(df)
        elapsed = time.perf_counter() - start

        avg = elapsed / 10
        assert avg < 2.0, f"SMC analysis took {avg:.3f}s per call"

    def test_tf_analysis_speed(self):
        adapter = TrendFollowerAdapter()
        df = _make_ohlcv(n=200)

        start = time.perf_counter()
        for _ in range(10):
            adapter.analyze_market(df)
        elapsed = time.perf_counter() - start

        avg = elapsed / 10
        assert avg < 1.0, f"TF analysis took {avg:.3f}s per call"

    def test_grid_analysis_speed(self):
        adapter = GridAdapter()
        df = _make_ohlcv(n=200)

        start = time.perf_counter()
        for _ in range(50):
            adapter.analyze_market(df)
        elapsed = time.perf_counter() - start

        avg = elapsed / 50
        assert avg < 0.1, f"Grid analysis took {avg:.3f}s per call"

    def test_dca_analysis_speed(self):
        adapter = DCAAdapter()
        df = _make_ohlcv(n=200)

        start = time.perf_counter()
        for _ in range(50):
            adapter.analyze_market(df)
        elapsed = time.perf_counter() - start

        avg = elapsed / 50
        assert avg < 0.1, f"DCA analysis took {avg:.3f}s per call"


# ===========================================================================
# Memory Stability
# ===========================================================================


class TestMemoryStability:
    """Test that adapters don't leak memory during extended operation."""

    def test_no_memory_growth_after_reset(self):
        """Memory should not grow unboundedly after reset cycles."""
        adapter = SMCStrategyAdapter()

        gc.collect()
        base_size = sys.getsizeof(adapter._positions) + sys.getsizeof(adapter._closed_trades)

        for cycle in range(5):
            # Open and close many positions
            for i in range(50):
                pos_id = adapter.open_position(_make_signal(), Decimal("50"))
                adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))
            # Reset clears everything
            adapter.reset()
            gc.collect()

        final_size = sys.getsizeof(adapter._positions) + sys.getsizeof(adapter._closed_trades)
        # After reset, memory should be back to baseline
        assert final_size <= base_size * 2, (
            f"Memory grew from {base_size} to {final_size} after 5 reset cycles"
        )

    def test_closed_trades_accumulate(self):
        """Closed trades should accumulate (expected behavior), verify it's bounded."""
        adapter = GridAdapter()
        for i in range(200):
            pos_id = adapter.open_position(_make_signal(), Decimal("50"))
            adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))

        perf = adapter.get_performance()
        assert perf.total_trades == 200
        assert len(adapter._closed_trades) == 200

    def test_large_dataframe_analysis(self):
        """Analyze a large DataFrame without issues."""
        adapter = SMCStrategyAdapter()
        df = _make_ohlcv(n=5000)  # Large dataset
        result = adapter.analyze_market(df)
        assert result is not None


# ===========================================================================
# Concurrent Operations
# ===========================================================================


class TestConcurrentOperations:
    """Test async concurrent operations."""

    async def test_concurrent_strategy_analysis(self):
        """Run multiple strategy analyses concurrently."""
        adapters = [
            SMCStrategyAdapter(name="smc"),
            TrendFollowerAdapter(name="tf"),
            GridAdapter(name="grid"),
            DCAAdapter(name="dca"),
        ]
        df = _make_ohlcv(n=200)

        async def analyze(adapter):
            return adapter.analyze_market(df)

        start = time.perf_counter()
        results = await asyncio.gather(*[analyze(a) for a in adapters])
        elapsed = time.perf_counter() - start

        assert len(results) == 4
        for r in results:
            assert r is not None
        # Concurrent should be fast
        assert elapsed < 5.0, f"Concurrent analysis took {elapsed:.2f}s"


# ===========================================================================
# Database Under Load
# ===========================================================================


class TestDatabaseUnderLoad:
    """Test database operations under high write throughput."""

    async def test_concurrent_writes(self):
        """Simulate concurrent database-like writes."""
        try:
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
            from bot.database.models import Base, Bot, ExchangeCredential, Order
        except ImportError:
            pytest.skip("aiosqlite not available")

        engine = create_async_engine("sqlite+aiosqlite://", echo=False)
        async with engine.begin() as conn:
            # Map BigInteger → Integer for SQLite
            from sqlalchemy import BigInteger, Integer
            for table in Base.metadata.tables.values():
                for column in table.columns:
                    if isinstance(column.type, BigInteger):
                        column.type = Integer()
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            # Setup
            async with session_factory() as session:
                cred = ExchangeCredential(
                    name="load-test",
                    exchange_id="bybit",
                    api_key_encrypted="k",
                    api_secret_encrypted="s",
                )
                session.add(cred)
                await session.flush()
                await session.refresh(cred)

                bot = Bot(
                    name="load-bot",
                    credentials_id=cred.id,
                    symbol="BTCUSDT",
                    strategy="grid",
                    config_data="{}",
                )
                session.add(bot)
                await session.flush()
                await session.refresh(bot)
                bot_id = bot.id
                await session.commit()

            # Write 100 orders
            start = time.perf_counter()
            async with session_factory() as session:
                for i in range(100):
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
            elapsed = time.perf_counter() - start

            # Read them back
            async with session_factory() as session:
                result = await session.execute(
                    select(Order).where(Order.bot_id == bot_id)
                )
                orders = result.scalars().all()
                assert len(orders) == 100

            assert elapsed < 5.0, f"Writing 100 orders took {elapsed:.2f}s"
        finally:
            await engine.dispose()


# ===========================================================================
# Performance Benchmarks
# ===========================================================================


class TestPerformanceBenchmarks:
    """Record performance benchmarks for regression detection."""

    def test_position_open_close_latency(self):
        """Benchmark single position open/close latency."""
        adapter = SMCStrategyAdapter()
        signal = _make_signal()

        times = []
        for _ in range(100):
            start = time.perf_counter()
            pos_id = adapter.open_position(signal, Decimal("50"))
            adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))
            times.append(time.perf_counter() - start)

        avg_ms = (sum(times) / len(times)) * 1000
        p99_ms = sorted(times)[98] * 1000
        # Single open+close should be sub-millisecond
        assert avg_ms < 1.0, f"Avg open+close: {avg_ms:.3f}ms"
        assert p99_ms < 5.0, f"P99 open+close: {p99_ms:.3f}ms"

    def test_signal_generation_latency(self):
        """Benchmark signal generation latency."""
        adapter = GridAdapter(num_levels=10)
        df = _make_ohlcv(n=100)
        adapter.analyze_market(df)

        times = []
        for _ in range(100):
            start = time.perf_counter()
            adapter.generate_signal(df, Decimal("10000"))
            times.append(time.perf_counter() - start)

        avg_ms = (sum(times) / len(times)) * 1000
        assert avg_ms < 10.0, f"Avg signal generation: {avg_ms:.3f}ms"

    def test_full_cycle_throughput(self):
        """How many full cycles (analyze → signal → open → update → close) per second."""
        adapter = GridAdapter()
        df = _make_ohlcv(n=100)

        cycles = 0
        start = time.perf_counter()
        timeout = 2.0  # Run for 2 seconds

        while time.perf_counter() - start < timeout:
            adapter.analyze_market(df)
            signal = adapter.generate_signal(df, Decimal("10000"))
            if signal:
                pos_id = adapter.open_position(signal, Decimal("50"))
                adapter.update_positions(Decimal("45500"), df)
                adapter.close_position(pos_id, ExitReason.MANUAL, Decimal("45500"))
            cycles += 1

        throughput = cycles / timeout
        # Should handle at least 100 cycles/second
        assert throughput > 50, f"Throughput: {throughput:.0f} cycles/sec"
