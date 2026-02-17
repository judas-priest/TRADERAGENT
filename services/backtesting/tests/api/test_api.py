"""Tests for FastAPI endpoints."""

import os
import pytest

from grid_backtester.api.app import create_app


@pytest.fixture
def client():
    # Ensure no auth required for tests
    os.environ.pop("BACKTESTER_API_KEY", None)
    app = create_app()
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "grid-backtester"
        assert "version" in data


class TestBacktestEndpoints:

    def test_submit_backtest_no_auth(self, client):
        resp = client.post("/api/v1/backtest/run", json={
            "symbol": "BTCUSDT",
            "num_levels": 10,
            "initial_balance": 10000,
        })
        # Should work without auth when BACKTESTER_API_KEY is not set
        assert resp.status_code in (200, 202, 422)

    def test_submit_backtest_returns_job_id(self, client):
        resp = client.post("/api/v1/backtest/run", json={
            "symbol": "BTCUSDT",
            "num_levels": 10,
            "initial_balance": 10000,
            "candles": [
                {"open": 45000, "high": 45100, "low": 44900, "close": 45050, "volume": 100},
                {"open": 45050, "high": 45150, "low": 44950, "close": 45100, "volume": 100},
                {"open": 45100, "high": 45200, "low": 45000, "close": 45150, "volume": 100},
            ],
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_get_nonexistent_job(self, client):
        resp = client.get("/api/v1/backtest/no-such-id")
        assert resp.status_code == 404

    def test_list_backtest_history(self, client):
        resp = client.get("/api/v1/backtest/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestOptimizeEndpoints:

    def test_submit_optimize(self, client):
        resp = client.post("/api/v1/optimize/run", json={
            "symbol": "BTCUSDT",
            "objective": "sharpe",
            "coarse_steps": 2,
            "fine_steps": 2,
            "candles": [
                {"open": 45000 + i * 10, "high": 45100 + i * 10, "low": 44900 + i * 10,
                 "close": 45050 + i * 10, "volume": 100}
                for i in range(20)
            ],
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"


class TestChartEndpoint:

    def test_chart_nonexistent_job(self, client):
        resp = client.get("/api/v1/chart/no-such-id")
        assert resp.status_code == 404


class TestPresetEndpoints:

    def test_list_presets(self, client):
        resp = client.get("/api/v1/presets")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_preset_not_found(self, client):
        resp = client.get("/api/v1/presets/NONEXIST")
        assert resp.status_code == 404

    def test_create_and_get_preset(self, client):
        resp = client.post("/api/v1/presets", json={
            "symbol": "BTCUSDT",
            "config_yaml": "num_levels: 15\nspacing: arithmetic",
            "cluster": "blue_chips",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "preset_id" in data
        assert data["symbol"] == "BTCUSDT"

        # Fetch by symbol
        resp2 = client.get("/api/v1/presets/BTCUSDT")
        assert resp2.status_code == 200
        assert resp2.json()["symbol"] == "BTCUSDT"

    def test_delete_preset(self, client):
        # Create first
        resp = client.post("/api/v1/presets", json={
            "symbol": "ETHUSDT",
            "config_yaml": "num_levels: 10",
        })
        assert resp.status_code == 201
        preset_id = resp.json()["preset_id"]

        # Delete
        resp2 = client.delete(f"/api/v1/presets/{preset_id}")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "deleted"

        # Verify gone
        resp3 = client.get("/api/v1/presets/ETHUSDT")
        assert resp3.status_code == 404

    def test_delete_preset_not_found(self, client):
        resp = client.delete("/api/v1/presets/nonexistent-id")
        assert resp.status_code == 404


class TestAuthEndpoint:

    def test_auth_required_when_key_set(self):
        os.environ["BACKTESTER_API_KEY"] = "test-secret-key"
        try:
            app = create_app()
            from fastapi.testclient import TestClient
            with TestClient(app) as c:
                # No auth header
                resp = c.get("/api/v1/presets")
                assert resp.status_code == 401

                # Wrong key
                resp = c.get("/api/v1/presets", headers={"X-API-Key": "wrong"})
                assert resp.status_code == 401

                # Correct key
                resp = c.get("/api/v1/presets", headers={"X-API-Key": "test-secret-key"})
                assert resp.status_code == 200
        finally:
            os.environ.pop("BACKTESTER_API_KEY", None)
