"""Tests for AlertHandler — AlertManager webhook receiver."""

import json
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from bot.monitoring.alert_handler import Alert, AlertHandler


# =============================================================================
# Alert Dataclass Tests
# =============================================================================


class TestAlert:
    """Tests for Alert dataclass."""

    def test_create(self):
        alert = Alert(
            name="BotDown",
            status="firing",
            severity="critical",
            summary="Bot is down",
            description="The trading bot has stopped responding",
            starts_at="2025-01-15T12:00:00Z",
            ends_at="0001-01-01T00:00:00Z",
        )
        assert alert.name == "BotDown"
        assert alert.status == "firing"
        assert alert.severity == "critical"

    def test_to_dict(self):
        alert = Alert(
            name="HighLatency",
            status="firing",
            severity="warning",
            summary="High API latency",
            description="Latency > 2s",
            starts_at="2025-01-15T12:00:00Z",
            ends_at="",
        )
        d = alert.to_dict()
        assert d["name"] == "HighLatency"
        assert d["severity"] == "warning"

    def test_format_message_firing(self):
        alert = Alert(
            name="CriticalDrawdown",
            status="firing",
            severity="critical",
            summary="Drawdown > 20%",
            description="Portfolio drawdown exceeded threshold",
            starts_at="",
            ends_at="",
        )
        msg = alert.format_message()
        assert "🚨" in msg
        assert "FIRING" in msg
        assert "CriticalDrawdown" in msg

    def test_format_message_resolved(self):
        alert = Alert(
            name="BotDown",
            status="resolved",
            severity="critical",
            summary="Bot recovered",
            description="",
            starts_at="",
            ends_at="",
        )
        msg = alert.format_message()
        assert "RESOLVED" in msg

    def test_format_message_warning(self):
        alert = Alert(
            name="HighLatency",
            status="firing",
            severity="warning",
            summary="test",
            description="",
            starts_at="",
            ends_at="",
        )
        msg = alert.format_message()
        assert "⚠️" in msg

    def test_format_message_info(self):
        alert = Alert(
            name="NoRecentTrades",
            status="firing",
            severity="info",
            summary="test",
            description="",
            starts_at="",
            ends_at="",
        )
        msg = alert.format_message()
        assert "ℹ️" in msg


# =============================================================================
# AlertHandler Unit Tests
# =============================================================================


class TestAlertHandlerUnit:
    """Unit tests for AlertHandler (no HTTP)."""

    def test_init(self):
        handler = AlertHandler()
        assert handler.alert_count == 0
        assert handler.history == []

    def test_add_callback(self):
        handler = AlertHandler()
        cb = AsyncMock()
        handler.add_callback(cb)
        assert len(handler._callbacks) == 1

    def test_parse_alerts(self):
        handler = AlertHandler()
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "BotDown",
                        "severity": "critical",
                    },
                    "annotations": {
                        "summary": "Bot is down",
                        "description": "Health check failed",
                    },
                    "startsAt": "2025-01-15T12:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                },
            ],
        }
        alerts = handler._parse_alerts(payload)
        assert len(alerts) == 1
        assert alerts[0].name == "BotDown"
        assert alerts[0].severity == "critical"
        assert alerts[0].summary == "Bot is down"

    def test_parse_multiple_alerts(self):
        handler = AlertHandler()
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Alert1", "severity": "warning"},
                    "annotations": {"summary": "First"},
                    "startsAt": "",
                    "endsAt": "",
                },
                {
                    "status": "resolved",
                    "labels": {"alertname": "Alert2", "severity": "critical"},
                    "annotations": {"summary": "Second"},
                    "startsAt": "",
                    "endsAt": "",
                },
            ],
        }
        alerts = handler._parse_alerts(payload)
        assert len(alerts) == 2
        assert alerts[0].name == "Alert1"
        assert alerts[1].status == "resolved"

    def test_add_to_history_max_size(self):
        handler = AlertHandler(max_history=3)
        for i in range(5):
            alert = Alert(
                name=f"Alert{i}",
                status="firing",
                severity="warning",
                summary="",
                description="",
                starts_at="",
                ends_at="",
            )
            handler._add_to_history(alert)
        assert len(handler.history) == 3
        # Most recent first
        assert handler.history[0].name == "Alert4"

    def test_get_status(self):
        handler = AlertHandler()
        status = handler.get_status()
        assert status["total_alerts"] == 0
        assert status["history_size"] == 0
        assert status["callback_count"] == 0


# =============================================================================
# AlertHandler HTTP Tests
# =============================================================================


class TestAlertHandlerHTTP:
    """Tests for AlertHandler HTTP endpoints."""

    async def test_webhook_valid_payload(self):
        handler = AlertHandler()
        callback = AsyncMock()
        handler.add_callback(callback)

        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            payload = {
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {"alertname": "TestAlert", "severity": "warning"},
                        "annotations": {"summary": "Test alert"},
                        "startsAt": "2025-01-15T12:00:00Z",
                        "endsAt": "",
                    },
                ],
            }
            resp = await client.post("/api/alerts", json=payload)
            assert resp.status == 200
            callback.assert_called_once()
            assert handler.alert_count == 1

    async def test_webhook_invalid_json(self):
        handler = AlertHandler()
        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/alerts",
                data=b"not json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400

    async def test_webhook_multiple_alerts(self):
        handler = AlertHandler()
        callback = AsyncMock()
        handler.add_callback(callback)

        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            payload = {
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {"alertname": "A1", "severity": "warning"},
                        "annotations": {},
                        "startsAt": "",
                        "endsAt": "",
                    },
                    {
                        "status": "resolved",
                        "labels": {"alertname": "A2", "severity": "critical"},
                        "annotations": {},
                        "startsAt": "",
                        "endsAt": "",
                    },
                ],
            }
            resp = await client.post("/api/alerts", json=payload)
            assert resp.status == 200
            assert callback.call_count == 2
            assert handler.alert_count == 2

    async def test_history_endpoint(self):
        handler = AlertHandler()
        # Add some alerts to history
        handler._add_to_history(Alert(
            name="TestAlert",
            status="firing",
            severity="warning",
            summary="Test",
            description="",
            starts_at="",
            ends_at="",
        ))

        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/alerts/history")
            assert resp.status == 200
            data = await resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "TestAlert"

    async def test_callback_error_doesnt_break(self):
        handler = AlertHandler()
        bad_callback = AsyncMock(side_effect=RuntimeError("callback failed"))
        handler.add_callback(bad_callback)

        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            payload = {
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {"alertname": "Test", "severity": "info"},
                        "annotations": {},
                        "startsAt": "",
                        "endsAt": "",
                    },
                ],
            }
            resp = await client.post("/api/alerts", json=payload)
            assert resp.status == 200  # Should still return 200
