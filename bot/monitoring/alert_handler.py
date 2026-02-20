"""
AlertHandler — Receives and processes alerts from Prometheus AlertManager.

Provides an aiohttp endpoint at /api/alerts to receive webhook alerts
and forward them to configured notification channels.

Usage:
    handler = AlertHandler()
    handler.add_callback(my_callback_fn)
    # Mount handler.routes in an aiohttp app
"""

import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web

from bot.utils.logger import get_logger

logger = get_logger(__name__)

# Type alias for alert callback
AlertCallback = Callable[["Alert"], Coroutine[Any, Any, None]]


@dataclass
class Alert:
    """Parsed alert from AlertManager webhook."""

    name: str
    status: str  # "firing" or "resolved"
    severity: str
    summary: str
    description: str
    starts_at: str
    ends_at: str
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "severity": self.severity,
            "summary": self.summary,
            "description": self.description,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
        }

    def format_message(self) -> str:
        """Format alert as human-readable message."""
        emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(self.severity, "🔔")
        status_text = "FIRING" if self.status == "firing" else "RESOLVED"
        return (
            f"{emoji} [{status_text}] {self.name}\n"
            f"Severity: {self.severity}\n"
            f"{self.summary}\n"
            f"{self.description}"
        )


class AlertHandler:
    """
    Handles AlertManager webhook alerts.

    Parses incoming alerts and dispatches to registered callbacks.
    Maintains a history of recent alerts.
    """

    def __init__(self, max_history: int = 100) -> None:
        self._callbacks: list[AlertCallback] = []
        self._history: list[Alert] = []
        self._max_history = max_history
        self._alert_count = 0

    @property
    def routes(self) -> list[web.RouteDef]:
        """aiohttp routes to mount."""
        return [
            web.post("/api/alerts", self.handle_webhook),
            web.get("/api/alerts/history", self.handle_history),
        ]

    def add_callback(self, callback: AlertCallback) -> None:
        """Register a callback for incoming alerts."""
        self._callbacks.append(callback)

    @property
    def history(self) -> list[Alert]:
        """Recent alert history."""
        return list(self._history)

    @property
    def alert_count(self) -> int:
        return self._alert_count

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handle POST /api/alerts from AlertManager."""
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return web.Response(status=400, text="Invalid JSON")

        alerts = self._parse_alerts(payload)
        self._alert_count += len(alerts)

        for alert in alerts:
            self._add_to_history(alert)
            logger.info(
                "alert_received",
                name=alert.name,
                status=alert.status,
                severity=alert.severity,
            )
            for callback in self._callbacks:
                try:
                    await callback(alert)
                except Exception as e:
                    logger.error(
                        "alert_callback_failed",
                        error=str(e),
                        alert=alert.name,
                    )

        return web.Response(status=200, text="ok")

    async def handle_history(self, request: web.Request) -> web.Response:
        """Handle GET /api/alerts/history."""
        data = [a.to_dict() for a in self._history]
        return web.json_response(data)

    def _parse_alerts(self, payload: dict[str, Any]) -> list[Alert]:
        """Parse AlertManager webhook payload into Alert objects."""
        alerts = []
        status = payload.get("status", "firing")

        for alert_data in payload.get("alerts", []):
            labels = alert_data.get("labels", {})
            annotations = alert_data.get("annotations", {})

            alert = Alert(
                name=labels.get("alertname", "unknown"),
                status=alert_data.get("status", status),
                severity=labels.get("severity", "info"),
                summary=annotations.get("summary", ""),
                description=annotations.get("description", ""),
                starts_at=alert_data.get("startsAt", ""),
                ends_at=alert_data.get("endsAt", ""),
                labels=labels,
                annotations=annotations,
            )
            alerts.append(alert)

        return alerts

    def _add_to_history(self, alert: Alert) -> None:
        """Add alert to history, maintaining max size."""
        self._history.insert(0, alert)
        if len(self._history) > self._max_history:
            self._history = self._history[: self._max_history]

    def get_status(self) -> dict[str, Any]:
        """Get handler status."""
        return {
            "total_alerts": self._alert_count,
            "history_size": len(self._history),
            "callback_count": len(self._callbacks),
            "recent_alerts": [a.to_dict() for a in self._history[:5]],
        }
