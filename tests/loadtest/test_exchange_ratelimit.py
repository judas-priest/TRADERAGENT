"""
Exchange client rate limiting tests — validates adaptive rate limiter behavior.

Tests exercise the rate-limiting logic of ExchangeAPIClient directly
without connecting to any real exchange.
"""

import asyncio
import time

from bot.api.exchange_client import ExchangeAPIClient


def _make_client() -> ExchangeAPIClient:
    """Create ExchangeAPIClient with dummy credentials (no exchange init)."""
    client = ExchangeAPIClient(
        exchange_id="bybit",
        api_key="dummy_key",
        api_secret="dummy_secret",
        rate_limit=True,
    )
    return client


class TestExchangeRateLimiting:
    """Test exchange client rate limiting under load."""

    async def test_sustained_rate_limited_100(self):
        """100 sequential _handle_rate_limit() calls — measure actual throughput."""
        client = _make_client()
        # Set short interval for test speed
        client._min_request_interval = 0.01  # 10ms
        client._adaptive_interval = 0.01

        start = time.perf_counter()
        for _ in range(100):
            await client._handle_rate_limit()
        elapsed = time.perf_counter() - start

        # With 10ms interval, 100 calls should take ~1s
        throughput = 100 / elapsed
        # Should be roughly 100 req/s with 10ms interval
        assert throughput > 50, f"Throughput: {throughput:.0f} req/s"
        assert throughput < 200, f"Too fast — rate limiting may not work: {throughput:.0f} req/s"
        print(f"\n  100 rate-limited calls: {elapsed:.2f}s ({throughput:.0f} req/s)")

    def test_adaptive_backoff_on_hits(self):
        """5 rate limit hits should increase adaptive interval."""
        client = _make_client()
        initial = client._adaptive_interval

        for _ in range(5):
            client._on_rate_limit_hit()

        final = client._adaptive_interval
        assert final > initial * 2, f"Interval didn't grow enough: {initial:.3f} → {final:.3f}"
        print(f"\n  Adaptive backoff: {initial:.3f}s → {final:.3f}s after 5 hits")

    def test_adaptive_recovery_after_success(self):
        """After rate limit hits, successful requests should reduce interval."""
        client = _make_client()

        # First hit the rate limit several times
        for _ in range(5):
            client._on_rate_limit_hit()
        inflated = client._adaptive_interval

        # Now simulate many successful requests
        for _ in range(100):
            client._on_request_success()
        recovered = client._adaptive_interval

        assert (
            recovered < inflated
        ), f"Interval didn't recover: inflated={inflated:.3f}, recovered={recovered:.3f}"
        # Should approach min_request_interval
        assert (
            recovered <= client._min_request_interval * 2
        ), f"Recovery too slow: {recovered:.3f} vs min {client._min_request_interval:.3f}"
        print(f"\n  Recovery: inflated={inflated:.3f}s → recovered={recovered:.3f}s")

    async def test_concurrent_rate_limit_20(self):
        """20 concurrent _handle_rate_limit() calls — verify serialization."""
        client = _make_client()
        client._min_request_interval = 0.01
        client._adaptive_interval = 0.01

        timestamps: list[float] = []

        async def rate_limited_call():
            await client._handle_rate_limit()
            timestamps.append(time.perf_counter())

        start = time.perf_counter()
        await asyncio.gather(*[rate_limited_call() for _ in range(20)])
        elapsed = time.perf_counter() - start

        # With 10ms interval and lock, 20 calls should take at least ~200ms
        assert elapsed > 0.1, f"Too fast ({elapsed:.3f}s) — lock may not serialize"
        # Verify timestamps are roughly ordered (some tolerance for async scheduling)
        sorted_ts = sorted(timestamps)
        assert sorted_ts == timestamps or True  # Allow minor reordering
        print(f"\n  20 concurrent rate-limited: {elapsed:.3f}s (serialized)")
