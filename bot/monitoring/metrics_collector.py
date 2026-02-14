"""
MetricsCollector — Bridge between bot orchestrators and MetricsExporter.

Periodically collects live metrics from running bots and feeds them
to the Prometheus-compatible MetricsExporter.

Usage:
    collector = MetricsCollector(
        exporter=metrics_exporter,
        orchestrators={"bot1": orchestrator1},
    )
    await collector.start()
    # ...
    await collector.stop()
"""

import asyncio
import time
from typing import Any

from bot.monitoring.metrics_exporter import MetricsExporter
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """
    Collects metrics from BotOrchestrators and feeds MetricsExporter.

    Runs a periodic loop that queries each orchestrator for status
    and updates Prometheus metrics accordingly.
    """

    def __init__(
        self,
        exporter: MetricsExporter,
        orchestrators: dict[str, Any] | None = None,
        collect_interval: float = 15.0,
    ) -> None:
        """
        Args:
            exporter: MetricsExporter instance.
            orchestrators: dict of bot_name -> BotOrchestrator.
            collect_interval: Seconds between collection cycles.
        """
        self._exporter = exporter
        self._orchestrators: dict[str, Any] = orchestrators or {}
        self._collect_interval = collect_interval
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def exporter(self) -> MetricsExporter:
        return self._exporter

    @property
    def orchestrators(self) -> dict[str, Any]:
        return self._orchestrators

    def set_orchestrators(self, orchestrators: dict[str, Any]) -> None:
        """Update orchestrators dict (e.g. after bots added/removed)."""
        self._orchestrators = orchestrators

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start the periodic collection loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._collect_loop())
        logger.info(
            "metrics_collector_started",
            interval=self._collect_interval,
            bot_count=len(self._orchestrators),
        )

    async def stop(self) -> None:
        """Stop the collection loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("metrics_collector_stopped")

    async def _collect_loop(self) -> None:
        """Periodic collection loop."""
        while self._running:
            try:
                await self.collect_all()
                await asyncio.sleep(self._collect_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("metrics_collection_error", error=str(e))
                await asyncio.sleep(self._collect_interval)

    # =========================================================================
    # Collection
    # =========================================================================

    async def collect_all(self) -> None:
        """Collect metrics from all orchestrators."""
        total_active = 0

        for bot_name, orch in self._orchestrators.items():
            try:
                await self._collect_bot_metrics(bot_name, orch)
                total_active += 1
            except Exception as e:
                logger.warning(
                    "bot_metrics_collection_failed",
                    bot_name=bot_name,
                    error=str(e),
                )

        # Global metrics
        self._exporter.set_metric(
            "traderagent_active_deals",
            float(total_active),
            labels={"scope": "total"},
        )

    async def _collect_bot_metrics(self, bot_name: str, orch: Any) -> None:
        """Collect metrics from a single orchestrator."""
        labels = {"bot": bot_name}

        # Bot state (1=running, 0=not)
        is_running = 1.0 if orch.state.value == "running" else 0.0
        self._exporter.set_metric(
            "traderagent_strategy_active",
            is_running,
            labels=labels,
        )

        # Health status
        health_val = 1.0 if orch.state.value in ("running", "paused") else 0.0
        self._exporter.set_metric(
            "traderagent_health_status",
            health_val,
            labels=labels,
        )

        # Get full status
        try:
            status = await orch.get_status()
        except Exception:
            return

        # Current price
        if status.get("current_price"):
            try:
                price = float(status["current_price"])
                self._exporter.set_metric(
                    "traderagent_portfolio_value",
                    price,
                    labels=labels,
                )
            except (ValueError, TypeError):
                pass

        # Grid metrics
        if "grid" in status:
            grid = status["grid"]
            self._exporter.set_metric(
                "traderagent_grid_open_orders",
                float(grid.get("active_orders", 0)),
                labels=labels,
            )
            try:
                profit = float(grid.get("total_profit", 0))
                self._exporter.set_metric(
                    "traderagent_pnl_total",
                    profit,
                    labels={**labels, "strategy": "grid"},
                )
            except (ValueError, TypeError):
                pass

        # DCA metrics
        if "dca" in status:
            dca = status["dca"]
            if dca.get("has_position"):
                self._exporter.set_metric(
                    "traderagent_active_deals",
                    1.0,
                    labels={**labels, "strategy": "dca"},
                )
                self._exporter.increment(
                    "traderagent_dca_safety_orders_filled",
                    0,  # Don't actually increment, just ensure metric exists
                    labels=labels,
                )

        # Trend-Follower metrics
        if "trend_follower" in status:
            tf = status["trend_follower"]
            self._exporter.set_metric(
                "traderagent_active_deals",
                float(tf.get("active_positions", 0)),
                labels={**labels, "strategy": "trend_follower"},
            )
            stats = tf.get("statistics", {})
            if stats:
                self._exporter.set_metric(
                    "traderagent_total_trades",
                    float(stats.get("total_trades", 0)),
                    labels={**labels, "strategy": "trend_follower"},
                )
                try:
                    pnl = float(stats.get("total_pnl", 0))
                    self._exporter.set_metric(
                        "traderagent_pnl_total",
                        pnl,
                        labels={**labels, "strategy": "trend_follower"},
                    )
                except (ValueError, TypeError):
                    pass

        # Risk metrics
        if "risk" in status:
            risk = status["risk"]
            if risk.get("drawdown") is not None:
                try:
                    self._exporter.set_metric(
                        "traderagent_pnl_unrealized",
                        float(risk["drawdown"]),
                        labels=labels,
                    )
                except (ValueError, TypeError):
                    pass

        # Strategy registry
        if "strategy_registry" in status:
            reg = status["strategy_registry"]
            self._exporter.set_metric(
                "traderagent_active_deals",
                float(reg.get("active", 0)),
                labels={**labels, "scope": "strategies"},
            )

        # Health monitor
        if "health" in status:
            health = status["health"]
            overall = health.get("overall_status", "unknown")
            health_score = {
                "healthy": 1.0,
                "degraded": 0.5,
                "unhealthy": 0.0,
                "critical": 0.0,
            }.get(overall, 0.0)
            self._exporter.set_metric(
                "traderagent_health_status",
                health_score,
                labels={**labels, "detail": "health_monitor"},
            )

        # Market regime
        if "market_regime" in status:
            regime = status["market_regime"]
            self._exporter.increment(
                "traderagent_regime_changes_total",
                0,  # Ensure metric exists
                labels=labels,
            )

    # =========================================================================
    # Manual Updates (for event-driven metrics)
    # =========================================================================

    def record_trade(self, bot_name: str, strategy: str = "unknown") -> None:
        """Increment trade counter for a bot."""
        self._exporter.increment(
            "traderagent_total_trades",
            labels={"bot": bot_name, "strategy": strategy},
        )

    def record_api_latency(self, bot_name: str, latency_seconds: float) -> None:
        """Record API call latency."""
        self._exporter.set_metric(
            "traderagent_api_latency_seconds",
            latency_seconds,
            labels={"bot": bot_name},
        )

    def record_regime_change(self, bot_name: str) -> None:
        """Increment regime change counter."""
        self._exporter.increment(
            "traderagent_regime_changes_total",
            labels={"bot": bot_name},
        )

    def record_safety_order(self, bot_name: str) -> None:
        """Increment DCA safety order counter."""
        self._exporter.increment(
            "traderagent_dca_safety_orders_filled",
            labels={"bot": bot_name},
        )

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get collector status."""
        return {
            "running": self._running,
            "collect_interval": self._collect_interval,
            "bot_count": len(self._orchestrators),
            "bot_names": list(self._orchestrators.keys()),
            "exporter_status": self._exporter.get_status(),
        }
