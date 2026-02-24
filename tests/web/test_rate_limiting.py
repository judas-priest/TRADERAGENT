"""
Tests for rate limiting on Web API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_rate_limit(client: AsyncClient):
    """Login endpoint should be rate-limited to 5/min."""
    # Register a user first
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "ratelimit_user",
            "email": "rl@example.com",
            "password": "securepass123",
        },
    )

    # Make 5 requests (should all succeed or return 401)
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "ratelimit_user", "password": "securepass123"},
        )
        assert resp.status_code in (200, 401)

    # 6th request should be rate-limited
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "ratelimit_user", "password": "securepass123"},
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_register_rate_limit(client: AsyncClient):
    """Register endpoint should be rate-limited to 5/min."""
    for i in range(5):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": f"rl_reg_{i}",
                "email": f"rl_reg_{i}@example.com",
                "password": "securepass123",
            },
        )
        assert resp.status_code in (201, 409)

    # 6th request should be rate-limited
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "rl_reg_overflow",
            "email": "overflow@example.com",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_refresh_rate_limit(client: AsyncClient):
    """Refresh endpoint should be rate-limited to 5/min."""
    # 5 invalid refreshes (401s count towards the limit)
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "fake-token"},
        )
        assert resp.status_code == 401

    # 6th should be rate-limited
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "fake-token"},
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_returns_retry_after(client: AsyncClient):
    """Rate-limited responses should include Retry-After header."""
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            json={"username": "nouser", "password": "nopass123456"},
        )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nouser", "password": "nopass123456"},
    )
    assert resp.status_code == 429
    assert "retry-after" in resp.headers


@pytest.mark.asyncio
async def test_health_not_rate_limited_at_5(client: AsyncClient):
    """Health endpoint uses default 60/min, not the auth 5/min limit."""
    for _ in range(10):
        resp = await client.get("/health")
        assert resp.status_code == 200
