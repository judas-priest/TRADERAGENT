"""
Tests for bots API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_bots_unauthenticated(client: AsyncClient):
    """Unauthenticated request should fail."""
    resp = await client.get("/api/v1/bots")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_bots(auth_client: AsyncClient):
    """List bots should return bot data from orchestrators."""
    resp = await auth_client.get("/api/v1/bots")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "test_bot"
    assert data[0]["strategy"] == "grid"
    assert data[0]["symbol"] == "BTC/USDT"
    assert data[0]["status"] == "running"
    assert data[0]["total_trades"] == 42


@pytest.mark.asyncio
async def test_list_bots_filter_strategy(auth_client: AsyncClient):
    """Filter bots by strategy."""
    resp = await auth_client.get("/api/v1/bots?strategy=grid")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await auth_client.get("/api/v1/bots?strategy=dca")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_list_bots_filter_status(auth_client: AsyncClient):
    """Filter bots by status."""
    resp = await auth_client.get("/api/v1/bots?status=running")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await auth_client.get("/api/v1/bots?status=stopped")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_get_bot(auth_client: AsyncClient):
    """Get specific bot status."""
    resp = await auth_client.get("/api/v1/bots/test_bot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test_bot"
    assert data["strategy"] == "grid"
    assert data["total_trades"] == 42
    assert float(data["total_profit"]) == 1234.56


@pytest.mark.asyncio
async def test_get_bot_not_found(auth_client: AsyncClient):
    """Get non-existent bot should return 404."""
    resp = await auth_client.get("/api/v1/bots/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_bot(auth_client: AsyncClient, mock_orchestrator):
    """Start bot should call orchestrator.start()."""
    resp = await auth_client.post("/api/v1/bots/test_bot/start")
    assert resp.status_code == 200
    mock_orchestrator.start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_bot(auth_client: AsyncClient, mock_orchestrator):
    """Stop bot should call orchestrator.stop()."""
    resp = await auth_client.post("/api/v1/bots/test_bot/stop")
    assert resp.status_code == 200
    mock_orchestrator.stop.assert_called_once()


@pytest.mark.asyncio
async def test_pause_bot(auth_client: AsyncClient, mock_orchestrator):
    """Pause bot should call orchestrator.pause()."""
    resp = await auth_client.post("/api/v1/bots/test_bot/pause")
    assert resp.status_code == 200
    mock_orchestrator.pause.assert_called_once()


@pytest.mark.asyncio
async def test_resume_bot(auth_client: AsyncClient, mock_orchestrator):
    """Resume bot should call orchestrator.resume()."""
    resp = await auth_client.post("/api/v1/bots/test_bot/resume")
    assert resp.status_code == 200
    mock_orchestrator.resume.assert_called_once()


@pytest.mark.asyncio
async def test_emergency_stop(auth_client: AsyncClient, mock_orchestrator):
    """Emergency stop should call orchestrator.emergency_stop()."""
    resp = await auth_client.post("/api/v1/bots/test_bot/emergency-stop")
    assert resp.status_code == 200
    mock_orchestrator.emergency_stop.assert_called_once()


@pytest.mark.asyncio
async def test_start_bot_not_found(auth_client: AsyncClient):
    """Start non-existent bot should return 404."""
    resp = await auth_client.post("/api/v1/bots/nonexistent/start")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_positions(auth_client: AsyncClient):
    """Get positions should return position list."""
    resp = await auth_client.get("/api/v1/bots/test_bot/positions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_pnl(auth_client: AsyncClient):
    """Get PnL should return PnL metrics."""
    resp = await auth_client.get("/api/v1/bots/test_bot/pnl")
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_realized_pnl"]) == 1234.56
    assert data["total_trades"] == 42
    assert data["win_rate"] == 0.65


@pytest.mark.asyncio
async def test_dashboard_overview(auth_client: AsyncClient):
    """Dashboard overview should aggregate bot data."""
    resp = await auth_client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_bots"] == 1
    assert data["total_bots"] == 1
    assert data["total_trades"] == 42
    assert len(data["bots"]) == 1
