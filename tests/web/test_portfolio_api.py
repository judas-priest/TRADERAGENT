"""
Tests for Portfolio API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_portfolio_summary_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_summary(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/portfolio/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_balance" in data
    assert "total_realized_pnl" in data
    assert "total_unrealized_pnl" in data
    assert "active_bots" in data
    assert "allocation" in data
    assert isinstance(data["allocation"], list)


@pytest.mark.asyncio
async def test_portfolio_allocation(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/portfolio/allocation")
    assert resp.status_code == 200
    data = resp.json()
    assert "by_strategy" in data
    assert "by_bot" in data


@pytest.mark.asyncio
async def test_portfolio_history(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/portfolio/history")
    assert resp.status_code == 200
    data = resp.json()
    assert "history" in data


@pytest.mark.asyncio
async def test_portfolio_drawdown(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/portfolio/drawdown")
    assert resp.status_code == 200
    data = resp.json()
    assert "max_drawdown_pct" in data
    assert "current_drawdown_pct" in data


@pytest.mark.asyncio
async def test_portfolio_trades(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/portfolio/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
