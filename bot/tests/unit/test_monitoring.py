"""Tests for monitoring components: MetricsExporter, MetricsCollector, AlertHandler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, TestClient, TestServer

from bot.monitoring.alert_handler import Alert, AlertHandler
from bot.monitoring.metrics_collector import MetricsCollector
from bot.monitoring.metrics_exporter import MetricsExporter


# =========================================================================
# MetricsExporter Tests
# =========================================================================


class TestMetricsExporter:
    """Test MetricsExporter functionality."""

    def test_set_metric(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_portfolio_value", 10000.0)
        assert "traderagent_portfolio_value" in exporter.metrics
        assert exporter.metrics["traderagent_portfolio_value"][0].value == 10000.0

    def test_set_metric_with_labels(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_pnl_total", 500.0, {"bot": "bot1", "strategy": "grid"})
        exporter.set_metric("traderagent_pnl_total", 200.0, {"bot": "bot1", "strategy": "dca"})

        values = exporter.metrics["traderagent_pnl_total"]
        assert len(values) == 2
        assert values[0].value == 500.0
        assert values[1].value == 200.0

    def test_set_metric_replaces_same_labels(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_portfolio_value", 10000.0, {"bot": "bot1"})
        exporter.set_metric("traderagent_portfolio_value", 12000.0, {"bot": "bot1"})

        values = exporter.metrics["traderagent_portfolio_value"]
        assert len(values) == 1
        assert values[0].value == 12000.0

    def test_increment(self):
        exporter = MetricsExporter(port=0)
        exporter.increment("traderagent_total_trades")
        exporter.increment("traderagent_total_trades")
        exporter.increment("traderagent_total_trades", amount=3.0)

        assert exporter.metrics["traderagent_total_trades"][0].value == 5.0

    def test_increment_with_labels(self):
        exporter = MetricsExporter(port=0)
        exporter.increment("traderagent_total_trades", labels={"bot": "bot1"})
        exporter.increment("traderagent_total_trades", labels={"bot": "bot2"})
        exporter.increment("traderagent_total_trades", labels={"bot": "bot1"})

        values = exporter.metrics["traderagent_total_trades"]
        bot1_val = next(v for v in values if v.labels.get("bot") == "bot1")
        bot2_val = next(v for v in values if v.labels.get("bot") == "bot2")
        assert bot1_val.value == 2.0
        assert bot2_val.value == 1.0

    def test_remove_metric(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_portfolio_value", 10000.0)
        exporter.remove_metric("traderagent_portfolio_value")
        assert "traderagent_portfolio_value" not in exporter.metrics

    def test_clear(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_portfolio_value", 10000.0)
        exporter.increment("traderagent_total_trades")
        exporter.clear()
        assert len(exporter.metrics) == 0

    def test_format_metrics_prometheus_format(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_portfolio_value", 10000.0)
        exporter.set_metric("traderagent_total_trades", 42.0)

        output = exporter.format_metrics()
        assert "# HELP traderagent_portfolio_value" in output
        assert "# TYPE traderagent_portfolio_value gauge" in output
        assert "traderagent_portfolio_value 10000.0" in output
        assert "traderagent_total_trades 42.0" in output
        # Uptime auto-added
        assert "traderagent_bot_uptime_seconds" in output

    def test_format_metrics_with_labels(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_pnl_total", 500.0, {"bot": "bot1", "strategy": "grid"})

        output = exporter.format_metrics()
        assert 'traderagent_pnl_total{bot="bot1",strategy="grid"} 500.0' in output

    def test_get_status(self):
        exporter = MetricsExporter(port=9100)
        exporter.set_metric("traderagent_portfolio_value", 10000.0)
        exporter.set_metric("traderagent_total_trades", 5.0)

        status = exporter.get_status()
        assert status["port"] == 9100
        assert status["running"] is False  # Not started
        assert status["metric_count"] == 2
        assert "traderagent_portfolio_value" in status["metric_names"]

    @pytest.mark.asyncio
    async def test_start_stop(self):
        exporter = MetricsExporter(port=0)  # Port 0 = random free port
        await exporter.start()
        assert exporter._runner is not None
        await exporter.stop()
        assert exporter._runner is None

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        exporter = MetricsExporter(port=0)
        app = web.Application()
        app.router.add_get("/health", exporter._handle_health)
        app.router.add_get("/metrics", exporter._handle_metrics)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/health")
            assert resp.status == 200
            text = await resp.text()
            assert text == "ok"

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_portfolio_value", 10000.0)

        app = web.Application()
        app.router.add_get("/metrics", exporter._handle_metrics)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/metrics")
            assert resp.status == 200
            text = await resp.text()
            assert "traderagent_portfolio_value 10000.0" in text


# =========================================================================
# MetricsCollector Tests
# =========================================================================


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def _make_mock_orchestrator(self, state="running", status=None):
        """Create a mock orchestrator."""
        orch = MagicMock()
        orch.state = MagicMock()
        orch.state.value = state
        default_status = {
            "state": state,
            "current_price": "45000.0",
            "grid": {"active_orders": 5, "total_profit": "100.5"},
            "risk": {"drawdown": "0.02"},
            "health": {"overall_status": "healthy"},
            "market_regime": {"regime": "sideways"},
        }
        orch.get_status = AsyncMock(return_value=status or default_status)
        return orch

    def test_init(self):
        exporter = MetricsExporter(port=0)
        collector = MetricsCollector(exporter=exporter)
        assert collector.exporter is exporter
        assert len(collector.orchestrators) == 0

    def test_set_orchestrators(self):
        exporter = MetricsExporter(port=0)
        collector = MetricsCollector(exporter=exporter)
        orch = self._make_mock_orchestrator()
        collector.set_orchestrators({"bot1": orch})
        assert "bot1" in collector.orchestrators

    @pytest.mark.asyncio
    async def test_collect_all(self):
        exporter = MetricsExporter(port=0)
        orch = self._make_mock_orchestrator()
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"bot1": orch},
        )

        await collector.collect_all()

        # Check metrics were set
        metrics = exporter.metrics
        assert "traderagent_strategy_active" in metrics
        assert "traderagent_health_status" in metrics
        assert "traderagent_portfolio_value" in metrics
        assert "traderagent_grid_open_orders" in metrics
        assert "traderagent_active_deals" in metrics

    @pytest.mark.asyncio
    async def test_collect_handles_errors(self):
        exporter = MetricsExporter(port=0)
        orch = self._make_mock_orchestrator()
        orch.get_status = AsyncMock(side_effect=Exception("connection lost"))

        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"bot1": orch},
        )

        # Should not raise
        await collector.collect_all()

    @pytest.mark.asyncio
    async def test_start_stop(self):
        exporter = MetricsExporter(port=0)
        collector = MetricsCollector(
            exporter=exporter,
            collect_interval=0.1,
        )

        await collector.start()
        assert collector._running is True
        assert collector._task is not None

        await asyncio.sleep(0.05)
        await collector.stop()
        assert collector._running is False

    def test_record_trade(self):
        exporter = MetricsExporter(port=0)
        collector = MetricsCollector(exporter=exporter)
        collector.record_trade("bot1", "grid")

        metrics = exporter.metrics
        assert "traderagent_total_trades" in metrics

    def test_record_api_latency(self):
        exporter = MetricsExporter(port=0)
        collector = MetricsCollector(exporter=exporter)
        collector.record_api_latency("bot1", 0.125)

        values = exporter.metrics["traderagent_api_latency_seconds"]
        assert values[0].value == 0.125

    def test_record_regime_change(self):
        exporter = MetricsExporter(port=0)
        collector = MetricsCollector(exporter=exporter)
        collector.record_regime_change("bot1")
        collector.record_regime_change("bot1")

        values = exporter.metrics["traderagent_regime_changes_total"]
        assert values[0].value == 2.0

    def test_record_safety_order(self):
        exporter = MetricsExporter(port=0)
        collector = MetricsCollector(exporter=exporter)
        collector.record_safety_order("bot1")

        assert "traderagent_dca_safety_orders_filled" in exporter.metrics

    def test_get_status(self):
        exporter = MetricsExporter(port=0)
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"bot1": MagicMock()},
        )

        status = collector.get_status()
        assert status["running"] is False
        assert status["bot_count"] == 1
        assert "bot1" in status["bot_names"]

    @pytest.mark.asyncio
    async def test_collect_with_dca_status(self):
        exporter = MetricsExporter(port=0)
        orch = self._make_mock_orchestrator(
            status={
                "state": "running",
                "current_price": "45000.0",
                "dca": {"has_position": True},
                "risk": {},
                "health": {"overall_status": "healthy"},
            }
        )

        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"bot1": orch},
        )
        await collector.collect_all()
        assert "traderagent_active_deals" in exporter.metrics

    @pytest.mark.asyncio
    async def test_collect_with_trend_follower_status(self):
        exporter = MetricsExporter(port=0)
        orch = self._make_mock_orchestrator(
            status={
                "state": "running",
                "current_price": "45000.0",
                "trend_follower": {
                    "active_positions": 2,
                    "statistics": {"total_trades": 15, "total_pnl": "350.0"},
                },
                "risk": {},
                "health": {"overall_status": "healthy"},
            }
        )

        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"bot1": orch},
        )
        await collector.collect_all()
        assert "traderagent_total_trades" in exporter.metrics

    @pytest.mark.asyncio
    async def test_collect_with_strategy_registry(self):
        exporter = MetricsExporter(port=0)
        orch = self._make_mock_orchestrator(
            status={
                "state": "running",
                "strategy_registry": {"total": 3, "active": 2},
                "risk": {},
                "health": {"overall_status": "degraded"},
            }
        )

        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"bot1": orch},
        )
        await collector.collect_all()
        assert "traderagent_health_status" in exporter.metrics


# =========================================================================
# AlertHandler Tests
# =========================================================================


class TestAlertHandler:
    """Test AlertHandler functionality."""

    def test_init(self):
        handler = AlertHandler()
        assert handler.alert_count == 0
        assert len(handler.history) == 0

    def test_add_callback(self):
        handler = AlertHandler()

        async def dummy(alert):
            pass

        handler.add_callback(dummy)
        assert len(handler._callbacks) == 1

    def test_parse_alerts(self):
        handler = AlertHandler()
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "BotDown", "severity": "critical"},
                    "annotations": {
                        "summary": "Bot is down",
                        "description": "Trading bot has been unreachable for 5 minutes",
                    },
                    "startsAt": "2026-02-16T12:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                }
            ],
        }

        alerts = handler._parse_alerts(payload)
        assert len(alerts) == 1
        assert alerts[0].name == "BotDown"
        assert alerts[0].severity == "critical"
        assert alerts[0].status == "firing"
        assert alerts[0].summary == "Bot is down"

    @pytest.mark.asyncio
    async def test_handle_webhook(self):
        handler = AlertHandler()
        received = []

        async def callback(alert):
            received.append(alert)

        handler.add_callback(callback)

        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/alerts",
                json={
                    "status": "firing",
                    "alerts": [
                        {
                            "status": "firing",
                            "labels": {"alertname": "HighLatency", "severity": "warning"},
                            "annotations": {
                                "summary": "API latency high",
                                "description": "Latency > 1s",
                            },
                            "startsAt": "2026-02-16T12:00:00Z",
                            "endsAt": "0001-01-01T00:00:00Z",
                        }
                    ],
                },
            )
            assert resp.status == 200

        assert len(received) == 1
        assert received[0].name == "HighLatency"
        assert handler.alert_count == 1

    @pytest.mark.asyncio
    async def test_handle_webhook_invalid_json(self):
        handler = AlertHandler()
        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/alerts",
                data="not json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_history_endpoint(self):
        handler = AlertHandler()

        # Add an alert to history
        alert = Alert(
            name="TestAlert",
            status="firing",
            severity="info",
            summary="Test",
            description="Test alert",
            starts_at="2026-02-16T12:00:00Z",
            ends_at="",
        )
        handler._add_to_history(alert)

        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/alerts/history")
            assert resp.status == 200
            data = await resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "TestAlert"

    def test_history_max_size(self):
        handler = AlertHandler(max_history=5)

        for i in range(10):
            alert = Alert(
                name=f"Alert{i}",
                status="firing",
                severity="info",
                summary=f"Test {i}",
                description="",
                starts_at="",
                ends_at="",
            )
            handler._add_to_history(alert)

        assert len(handler.history) == 5
        # Most recent should be first
        assert handler.history[0].name == "Alert9"

    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        handler = AlertHandler()

        async def bad_callback(alert):
            raise ValueError("callback failed")

        async def good_callback(alert):
            pass

        handler.add_callback(bad_callback)
        handler.add_callback(good_callback)

        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/alerts",
                json={
                    "status": "firing",
                    "alerts": [
                        {
                            "labels": {"alertname": "Test", "severity": "info"},
                            "annotations": {"summary": "", "description": ""},
                            "startsAt": "",
                            "endsAt": "",
                        }
                    ],
                },
            )
            # Should succeed even if callback fails
            assert resp.status == 200

    def test_alert_format_message(self):
        alert = Alert(
            name="BotDown",
            status="firing",
            severity="critical",
            summary="Bot is down",
            description="Trading bot unreachable",
            starts_at="2026-02-16T12:00:00Z",
            ends_at="",
        )

        msg = alert.format_message()
        assert "🚨" in msg  # critical emoji
        assert "FIRING" in msg
        assert "BotDown" in msg
        assert "Bot is down" in msg

    def test_alert_format_resolved(self):
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

    def test_get_status(self):
        handler = AlertHandler()
        status = handler.get_status()
        assert status["total_alerts"] == 0
        assert status["history_size"] == 0
        assert status["callback_count"] == 0


# =========================================================================
# Integration: Alert→Telegram Bridge
# =========================================================================


class TestAlertTelegramBridge:
    """Test alert-to-telegram forwarding."""

    @pytest.mark.asyncio
    async def test_bridge_callback(self):
        """Test that AlertHandler callback forwards to Telegram."""
        sent_messages = []

        mock_bot = MagicMock()

        async def mock_send(chat_id, text):
            sent_messages.append({"chat_id": chat_id, "text": text})

        mock_bot.send_message = mock_send

        handler = AlertHandler()
        allowed_chat_ids = [12345, 67890]

        async def send_alert(alert: Alert) -> None:
            message = alert.format_message()
            for chat_id in allowed_chat_ids:
                await mock_bot.send_message(chat_id=chat_id, text=message)

        handler.add_callback(send_alert)

        app = web.Application()
        app.router.add_routes(handler.routes)

        async with TestClient(TestServer(app)) as client:
            await client.post(
                "/api/alerts",
                json={
                    "status": "firing",
                    "alerts": [
                        {
                            "labels": {"alertname": "LargeDrawdown", "severity": "warning"},
                            "annotations": {
                                "summary": "Drawdown > 10%",
                                "description": "Check positions",
                            },
                            "startsAt": "2026-02-16T12:00:00Z",
                            "endsAt": "",
                        }
                    ],
                },
            )

        assert len(sent_messages) == 2
        assert sent_messages[0]["chat_id"] == 12345
        assert sent_messages[1]["chat_id"] == 67890
        assert "LargeDrawdown" in sent_messages[0]["text"]
