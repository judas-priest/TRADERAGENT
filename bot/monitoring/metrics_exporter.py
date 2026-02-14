"""
MetricsExporter — Prometheus-compatible metrics HTTP endpoint.

Exposes bot trading metrics in Prometheus text format on /metrics.
No external prometheus_client dependency — uses plain text format.

Usage:
    exporter = MetricsExporter(port=9100)
    exporter.set_metric("traderagent_portfolio_value", 10000.0)
    exporter.increment("traderagent_total_trades")
    await exporter.start()
    # ...
    await exporter.stop()
"""

import time
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web

from bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MetricValue:
    """Single metric with optional labels."""

    value: float
    labels: dict[str, str] = field(default_factory=dict)
    help_text: str = ""
    metric_type: str = "gauge"  # gauge, counter


# Standard metric definitions
METRIC_DEFINITIONS: dict[str, tuple[str, str]] = {
    "traderagent_portfolio_value": ("gauge", "Current portfolio value in quote currency"),
    "traderagent_active_deals": ("gauge", "Number of currently active deals"),
    "traderagent_total_trades": ("counter", "Total number of executed trades"),
    "traderagent_pnl_total": ("gauge", "Total realized PnL"),
    "traderagent_pnl_unrealized": ("gauge", "Total unrealized PnL"),
    "traderagent_api_latency_seconds": ("gauge", "Last API call latency in seconds"),
    "traderagent_bot_uptime_seconds": ("gauge", "Bot uptime in seconds"),
    "traderagent_strategy_active": ("gauge", "Whether strategy is active (1=yes, 0=no)"),
    "traderagent_health_status": ("gauge", "Bot health status (1=healthy, 0=unhealthy)"),
    "traderagent_grid_open_orders": ("gauge", "Number of open grid orders"),
    "traderagent_dca_safety_orders_filled": ("counter", "Total safety orders filled"),
    "traderagent_regime_changes_total": ("counter", "Total market regime changes"),
}


class MetricsExporter:
    """
    HTTP server that exposes Prometheus-format metrics on /metrics.

    Thread-safe metric updates via simple dict operations.
    Supports labeled metrics (e.g., per-strategy, per-pair).
    """

    def __init__(self, port: int = 9100, host: str = "0.0.0.0") -> None:
        self._port = port
        self._host = host
        self._metrics: dict[str, list[MetricValue]] = {}
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._start_time = time.time()

    @property
    def port(self) -> int:
        return self._port

    @property
    def metrics(self) -> dict[str, list[MetricValue]]:
        """Copy of current metrics."""
        return {k: list(v) for k, v in self._metrics.items()}

    # =========================================================================
    # Metric Operations
    # =========================================================================

    def set_metric(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Set a metric value, replacing any existing value with matching labels.

        Args:
            name: Metric name (e.g., "traderagent_portfolio_value").
            value: Numeric value.
            labels: Optional label dict (e.g., {"strategy": "grid", "pair": "BTCUSDT"}).
        """
        labels = labels or {}
        metric = MetricValue(value=value, labels=labels)

        # Set type/help from definitions
        if name in METRIC_DEFINITIONS:
            metric.metric_type, metric.help_text = METRIC_DEFINITIONS[name]

        if name not in self._metrics:
            self._metrics[name] = [metric]
            return

        # Replace existing metric with same labels
        for i, existing in enumerate(self._metrics[name]):
            if existing.labels == labels:
                self._metrics[name][i] = metric
                return

        # New label combination
        self._metrics[name].append(metric)

    def increment(
        self,
        name: str,
        amount: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Increment a counter metric.

        Args:
            name: Metric name.
            amount: Amount to add (default 1.0).
            labels: Optional labels.
        """
        labels = labels or {}

        if name in self._metrics:
            for metric in self._metrics[name]:
                if metric.labels == labels:
                    metric.value += amount
                    return

        # First time — initialize
        self.set_metric(name, amount, labels)

    def remove_metric(self, name: str) -> None:
        """Remove all values for a metric."""
        self._metrics.pop(name, None)

    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()

    # =========================================================================
    # Prometheus Format
    # =========================================================================

    def format_metrics(self) -> str:
        """
        Format all metrics in Prometheus text exposition format.

        Returns:
            String in Prometheus format.
        """
        lines: list[str] = []

        # Auto-add uptime
        uptime = time.time() - self._start_time
        self.set_metric("traderagent_bot_uptime_seconds", uptime)

        seen_headers: set[str] = set()

        for name, values in sorted(self._metrics.items()):
            # HELP and TYPE headers (once per metric name)
            if name not in seen_headers:
                seen_headers.add(name)
                help_text = ""
                metric_type = "gauge"
                if values:
                    help_text = values[0].help_text
                    metric_type = values[0].metric_type
                if name in METRIC_DEFINITIONS:
                    metric_type, help_text = METRIC_DEFINITIONS[name]

                if help_text:
                    lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} {metric_type}")

            # Metric values
            for mv in values:
                if mv.labels:
                    label_str = ",".join(
                        f'{k}="{v}"' for k, v in sorted(mv.labels.items())
                    )
                    lines.append(f"{name}{{{label_str}}} {mv.value}")
                else:
                    lines.append(f"{name} {mv.value}")

        return "\n".join(lines) + "\n"

    # =========================================================================
    # HTTP Server
    # =========================================================================

    async def start(self) -> None:
        """Start the HTTP metrics server."""
        self._app = web.Application()
        self._app.router.add_get("/metrics", self._handle_metrics)
        self._app.router.add_get("/health", self._handle_health)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()

        logger.info(
            "metrics_exporter_started",
            host=self._host,
            port=self._port,
        )

    async def stop(self) -> None:
        """Stop the HTTP metrics server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._app = None
            logger.info("metrics_exporter_stopped")

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle GET /metrics — return Prometheus format."""
        body = self.format_metrics()
        return web.Response(
            text=body,
            content_type="text/plain",
            charset="utf-8",
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle GET /health — simple health check."""
        return web.Response(text="ok", content_type="text/plain")

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get exporter status."""
        return {
            "port": self._port,
            "host": self._host,
            "running": self._runner is not None,
            "metric_count": sum(len(v) for v in self._metrics.values()),
            "metric_names": sorted(self._metrics.keys()),
            "uptime_seconds": round(time.time() - self._start_time, 1),
        }
