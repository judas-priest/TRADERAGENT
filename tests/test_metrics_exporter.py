"""Tests for MetricsExporter — Prometheus metrics HTTP endpoint."""

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from bot.monitoring.metrics_exporter import (
    METRIC_DEFINITIONS,
    MetricsExporter,
)

# =============================================================================
# Unit Tests (no HTTP server)
# =============================================================================


class TestMetricOperations:
    """Tests for metric set/increment/remove operations."""

    def test_set_metric(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_portfolio_value", 10000.0)

        metrics = exporter.metrics
        assert "traderagent_portfolio_value" in metrics
        assert metrics["traderagent_portfolio_value"][0].value == 10000.0

    def test_set_metric_with_labels(self):
        exporter = MetricsExporter()
        exporter.set_metric(
            "traderagent_active_deals",
            3.0,
            labels={"strategy": "grid", "pair": "BTCUSDT"},
        )

        metrics = exporter.metrics
        mv = metrics["traderagent_active_deals"][0]
        assert mv.value == 3.0
        assert mv.labels == {"strategy": "grid", "pair": "BTCUSDT"}

    def test_set_metric_replaces_same_labels(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_pnl_total", 100.0)
        exporter.set_metric("traderagent_pnl_total", 200.0)

        metrics = exporter.metrics
        assert len(metrics["traderagent_pnl_total"]) == 1
        assert metrics["traderagent_pnl_total"][0].value == 200.0

    def test_set_metric_different_labels_adds(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_active_deals", 2.0, {"strategy": "grid"})
        exporter.set_metric("traderagent_active_deals", 1.0, {"strategy": "dca"})

        metrics = exporter.metrics
        assert len(metrics["traderagent_active_deals"]) == 2

    def test_increment(self):
        exporter = MetricsExporter()
        exporter.increment("traderagent_total_trades")
        exporter.increment("traderagent_total_trades")
        exporter.increment("traderagent_total_trades", 3.0)

        metrics = exporter.metrics
        assert metrics["traderagent_total_trades"][0].value == 5.0

    def test_increment_with_labels(self):
        exporter = MetricsExporter()
        exporter.increment("traderagent_total_trades", labels={"pair": "BTCUSDT"})
        exporter.increment("traderagent_total_trades", labels={"pair": "ETHUSDT"})
        exporter.increment("traderagent_total_trades", labels={"pair": "BTCUSDT"})

        metrics = exporter.metrics
        values = metrics["traderagent_total_trades"]
        btc = next(v for v in values if v.labels.get("pair") == "BTCUSDT")
        eth = next(v for v in values if v.labels.get("pair") == "ETHUSDT")
        assert btc.value == 2.0
        assert eth.value == 1.0

    def test_remove_metric(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_pnl_total", 100.0)
        exporter.remove_metric("traderagent_pnl_total")

        assert "traderagent_pnl_total" not in exporter.metrics

    def test_clear(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_pnl_total", 100.0)
        exporter.set_metric("traderagent_active_deals", 5.0)
        exporter.clear()

        assert len(exporter.metrics) == 0


class TestPrometheusFormat:
    """Tests for Prometheus text format output."""

    def test_format_basic_metric(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_health_status", 1.0)

        output = exporter.format_metrics()
        assert "traderagent_health_status 1.0" in output

    def test_format_includes_help(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_portfolio_value", 10000.0)

        output = exporter.format_metrics()
        assert "# HELP traderagent_portfolio_value" in output
        assert "# TYPE traderagent_portfolio_value gauge" in output

    def test_format_counter_type(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_total_trades", 42.0)

        output = exporter.format_metrics()
        assert "# TYPE traderagent_total_trades counter" in output

    def test_format_with_labels(self):
        exporter = MetricsExporter()
        exporter.set_metric(
            "traderagent_active_deals",
            3.0,
            {"strategy": "grid"},
        )

        output = exporter.format_metrics()
        assert 'traderagent_active_deals{strategy="grid"} 3.0' in output

    def test_format_multiple_labels_sorted(self):
        exporter = MetricsExporter()
        exporter.set_metric(
            "traderagent_active_deals",
            2.0,
            {"strategy": "dca", "pair": "BTCUSDT"},
        )

        output = exporter.format_metrics()
        assert 'pair="BTCUSDT",strategy="dca"' in output

    def test_format_includes_uptime(self):
        exporter = MetricsExporter()
        output = exporter.format_metrics()
        assert "traderagent_bot_uptime_seconds" in output

    def test_format_ends_with_newline(self):
        exporter = MetricsExporter()
        exporter.set_metric("traderagent_health_status", 1.0)
        output = exporter.format_metrics()
        assert output.endswith("\n")


class TestMetricDefinitions:
    """Tests for metric definitions."""

    def test_definitions_exist(self):
        assert len(METRIC_DEFINITIONS) > 0

    def test_all_definitions_have_type_and_help(self):
        for name, (mtype, help_text) in METRIC_DEFINITIONS.items():
            assert mtype in ("gauge", "counter"), f"{name} has invalid type: {mtype}"
            assert len(help_text) > 0, f"{name} has empty help text"


class TestExporterStatus:
    """Tests for exporter status reporting."""

    def test_get_status(self):
        exporter = MetricsExporter(port=9200)
        exporter.set_metric("traderagent_health_status", 1.0)

        status = exporter.get_status()
        assert status["port"] == 9200
        assert status["running"] is False
        assert status["metric_count"] == 1
        assert "traderagent_health_status" in status["metric_names"]


class TestHTTPEndpoints:
    """Tests for HTTP /metrics and /health endpoints."""

    async def test_metrics_endpoint(self):
        exporter = MetricsExporter(port=0)
        exporter.set_metric("traderagent_health_status", 1.0)

        app = web.Application()
        app.router.add_get("/metrics", exporter._handle_metrics)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/metrics")
            assert resp.status == 200
            text = await resp.text()
            assert "traderagent_health_status" in text
            assert "text/plain" in resp.content_type

    async def test_health_endpoint(self):
        exporter = MetricsExporter(port=0)

        app = web.Application()
        app.router.add_get("/health", exporter._handle_health)

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/health")
            assert resp.status == 200
            text = await resp.text()
            assert text == "ok"

    async def test_start_stop(self):
        exporter = MetricsExporter(port=19876)
        await exporter.start()
        assert exporter._runner is not None
        await exporter.stop()
        assert exporter._runner is None
