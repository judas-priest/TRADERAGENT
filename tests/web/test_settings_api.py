"""
Tests for Settings API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_settings_config_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/settings/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_config(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/settings/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "monitoring" in data
    assert "web" in data


@pytest.mark.asyncio
async def test_get_notifications(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/settings/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert "notify_on_trade" in data
    assert "notify_on_error" in data
    assert "notify_on_alert" in data
    assert "telegram_configured" in data


@pytest.mark.asyncio
async def test_update_notifications(auth_client: AsyncClient):
    resp = await auth_client.put(
        "/api/v1/settings/notifications",
        json={
            "notify_on_trade": False,
            "notify_on_error": True,
            "notify_on_alert": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Notifications updated"


@pytest.mark.asyncio
async def test_dashboard_overview_has_data(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_bots"] == 1
    assert "active_bots" in data
    assert "total_trades" in data
    assert "bots" in data
    assert len(data["bots"]) == 1
    bot = data["bots"][0]
    assert bot["name"] == "test_bot"
    assert bot["strategy"] == "grid"
