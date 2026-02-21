"""
Tests for Strategies API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_strategy_types_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/strategies/types")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_strategy_types(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/strategies/types")
    assert resp.status_code == 200
    types = resp.json()
    assert len(types) == 4
    names = [t["name"] for t in types]
    assert "grid" in names
    assert "dca" in names
    assert "trend_follower" in names
    assert "smc" in names
    for t in types:
        assert "config_schema" in t
        assert "description" in t
        assert "coming_soon" in t


@pytest.mark.asyncio
async def test_strategy_types_coming_soon(auth_client: AsyncClient):
    """SMC strategy should be marked as coming_soon."""
    resp = await auth_client.get("/api/v1/strategies/types")
    assert resp.status_code == 200
    types = resp.json()
    by_name = {t["name"]: t for t in types}
    assert by_name["smc"]["coming_soon"] is True
    assert by_name["grid"]["coming_soon"] is False
    assert by_name["dca"]["coming_soon"] is False
    assert by_name["trend_follower"]["coming_soon"] is False


@pytest.mark.asyncio
async def test_list_templates_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/strategies/templates")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_template(auth_client: AsyncClient):
    resp = await auth_client.post(
        "/api/v1/strategies/templates",
        json={
            "name": "Conservative Grid",
            "description": "Low-risk grid strategy",
            "strategy_type": "grid",
            "config_json": '{"grid_levels": 10}',
            "risk_level": "low",
            "min_deposit": "100.00",
            "expected_pnl_pct": "5.0",
            "recommended_pairs": ["BTC/USDT"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Conservative Grid"
    assert data["risk_level"] == "low"
    assert data["copy_count"] == 0


@pytest.mark.asyncio
async def test_get_template(auth_client: AsyncClient):
    # Create first
    create_resp = await auth_client.post(
        "/api/v1/strategies/templates",
        json={
            "name": "DCA Strategy",
            "description": "DCA bot",
            "strategy_type": "dca",
            "config_json": "{}",
            "risk_level": "medium",
            "min_deposit": "500.00",
        },
    )
    assert create_resp.status_code == 201
    template_id = create_resp.json()["id"]

    # Get by ID
    resp = await auth_client.get(f"/api/v1/strategies/templates/{template_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "DCA Strategy"


@pytest.mark.asyncio
async def test_get_template_not_found(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/strategies/templates/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_copy_strategy(auth_client: AsyncClient):
    # Create template
    create_resp = await auth_client.post(
        "/api/v1/strategies/templates",
        json={
            "name": "Copy Test",
            "description": "For copy testing",
            "strategy_type": "grid",
            "config_json": "{}",
            "risk_level": "low",
            "min_deposit": "100.00",
        },
    )
    assert create_resp.status_code == 201
    template_id = create_resp.json()["id"]

    # Copy
    resp = await auth_client.post(
        "/api/v1/strategies/copy",
        json={
            "template_id": template_id,
            "bot_name": "my-copy-bot",
            "symbol": "ETH/USDT",
            "deposit_amount": "1000.00",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["bot_name"] == "my-copy-bot"


@pytest.mark.asyncio
async def test_copy_nonexistent_template(auth_client: AsyncClient):
    resp = await auth_client.post(
        "/api/v1/strategies/copy",
        json={
            "template_id": 99999,
            "bot_name": "bot",
            "symbol": "BTC/USDT",
            "deposit_amount": "500.00",
        },
    )
    assert resp.status_code == 404
