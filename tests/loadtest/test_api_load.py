"""
Web API load testing — concurrent HTTP requests to FastAPI endpoints.

Tests validate that the API handles concurrent load without errors or excessive latency.
"""

import asyncio
import time

from httpx import AsyncClient


class TestAPIEndpointLoad:
    """Test FastAPI endpoints under concurrent load."""

    async def test_concurrent_list_bots_50(self, auth_client: AsyncClient):
        """50 concurrent GET /api/v1/bots requests."""
        start = time.perf_counter()
        responses = await asyncio.gather(*[auth_client.get("/api/v1/bots") for _ in range(50)])
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in responses)
        assert elapsed < 5.0, f"50 concurrent /bots took {elapsed:.2f}s"
        print(f"\n  50 concurrent /bots: {elapsed:.2f}s ({50/elapsed:.0f} req/s)")

    async def test_concurrent_dashboard_50(self, auth_client: AsyncClient):
        """50 concurrent GET /api/v1/dashboard/overview requests."""
        start = time.perf_counter()
        responses = await asyncio.gather(
            *[auth_client.get("/api/v1/dashboard/overview") for _ in range(50)]
        )
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in responses)
        assert elapsed < 5.0, f"50 concurrent /dashboard took {elapsed:.2f}s"
        print(f"\n  50 concurrent /dashboard: {elapsed:.2f}s ({50/elapsed:.0f} req/s)")

    async def test_concurrent_bot_status_100(self, auth_client: AsyncClient):
        """100 concurrent GET /api/v1/bots/bot_0 requests."""
        start = time.perf_counter()
        responses = await asyncio.gather(
            *[auth_client.get("/api/v1/bots/bot_0") for _ in range(100)]
        )
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in responses)
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 100, f"Avg bot status: {avg_ms:.1f}ms"
        print(f"\n  100 concurrent /bots/bot_0: {elapsed:.2f}s (avg {avg_ms:.1f}ms)")

    async def test_concurrent_mixed_endpoints_100(self, auth_client: AsyncClient):
        """100 requests across mixed endpoints."""
        endpoints = [
            "/api/v1/bots",
            "/api/v1/dashboard/overview",
            "/api/v1/portfolio/summary",
            "/api/v1/bots/bot_0",
        ]

        start = time.perf_counter()
        responses = await asyncio.gather(
            *[auth_client.get(endpoints[i % len(endpoints)]) for i in range(100)]
        )
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in responses)
        assert elapsed < 10.0, f"100 mixed requests took {elapsed:.2f}s"
        print(f"\n  100 mixed endpoints: {elapsed:.2f}s ({100/elapsed:.0f} req/s)")

    async def test_sustained_throughput_200(self, auth_client: AsyncClient):
        """200 sequential GET /api/v1/bots — measure throughput."""
        start = time.perf_counter()
        for _ in range(200):
            resp = await auth_client.get("/api/v1/bots")
            assert resp.status_code == 200
        elapsed = time.perf_counter() - start

        throughput = 200 / elapsed
        assert throughput > 30, f"Throughput: {throughput:.0f} req/s (need >30)"
        print(f"\n  200 sequential /bots: {elapsed:.2f}s ({throughput:.0f} req/s)")

    async def test_concurrent_auth_10_users(self, client: AsyncClient):
        """10 unique users register + login concurrently.

        Note: bcrypt hashing is intentionally slow (~0.5-1s per hash),
        so 10 users × 2 hashes (register + login verify) ≈ 10-20s.
        """

        async def register_and_login(i: int):
            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": f"loaduser_{i}",
                    "email": f"loaduser_{i}@test.com",
                    "password": "testpassword123",
                },
            )
            login = await client.post(
                "/api/v1/auth/login",
                json={"username": f"loaduser_{i}", "password": "testpassword123"},
            )
            return reg.status_code, login.status_code

        start = time.perf_counter()
        results = await asyncio.gather(*[register_and_login(i) for i in range(10)])
        elapsed = time.perf_counter() - start

        # First user is auto-admin (201), rest may vary but login should work
        for reg_code, login_code in results:
            assert reg_code in (200, 201), f"Register failed: {reg_code}"
            assert login_code == 200, f"Login failed: {login_code}"
        assert elapsed < 30.0, f"10 auth flows took {elapsed:.2f}s"
        print(f"\n  10 concurrent auth: {elapsed:.2f}s")

    async def test_health_500_concurrent(self, client: AsyncClient):
        """500 concurrent GET /health (no auth required)."""
        start = time.perf_counter()
        responses = await asyncio.gather(*[client.get("/health") for _ in range(500)])
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in responses)
        assert elapsed < 3.0, f"500 /health took {elapsed:.2f}s"
        print(f"\n  500 concurrent /health: {elapsed:.2f}s ({500/elapsed:.0f} req/s)")

    async def test_concurrent_portfolio_50(self, auth_client: AsyncClient):
        """50 concurrent GET /api/v1/portfolio/summary requests."""
        start = time.perf_counter()
        responses = await asyncio.gather(
            *[auth_client.get("/api/v1/portfolio/summary") for _ in range(50)]
        )
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in responses)
        assert elapsed < 5.0, f"50 concurrent /portfolio took {elapsed:.2f}s"
        print(f"\n  50 concurrent /portfolio: {elapsed:.2f}s ({50/elapsed:.0f} req/s)")
