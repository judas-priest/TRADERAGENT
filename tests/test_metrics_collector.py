"""Tests for MetricsCollector — bridge between orchestrators and MetricsExporter."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.monitoring.metrics_collector import MetricsCollector
from bot.monitoring.metrics_exporter import MetricsExporter

# =============================================================================
# Fixtures
# =============================================================================


def _make_orchestrator(
    name: str = "test_bot",
    state: str = "running",
    current_price: str = "50000",
) -> MagicMock:
    """Create a mock BotOrchestrator."""
    orch = MagicMock()
    orch.state = MagicMock()
    orch.state.value = state
    orch.current_price = Decimal(current_price) if current_price else None
    orch.config = MagicMock()
    orch.config.name = name
    orch.config.symbol = "BTC/USDT"

    orch.get_status = AsyncMock(
        return_value={
            "bot_name": name,
            "symbol": "BTC/USDT",
            "strategy": "grid",
            "state": state,
            "current_price": current_price,
            "dry_run": True,
            "version": "2.0",
            "strategy_registry": {"total": 1, "active": 1},
            "health": {"overall_status": "healthy"},
        }
    )

    return orch


@pytest.fixture
def exporter():
    return MetricsExporter()


@pytest.fixture
def collector(exporter):
    orch = _make_orchestrator()
    return MetricsCollector(
        exporter=exporter,
        orchestrators={"test_bot": orch},
        collect_interval=1.0,
    )


# =============================================================================
# Init Tests
# =============================================================================


class TestInit:
    """Tests for MetricsCollector initialization."""

    def test_init(self, exporter):
        collector = MetricsCollector(exporter=exporter)
        assert collector.exporter is exporter
        assert collector.orchestrators == {}

    def test_init_with_orchestrators(self, exporter):
        orch = _make_orchestrator()
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"bot1": orch},
        )
        assert "bot1" in collector.orchestrators

    def test_set_orchestrators(self, exporter):
        collector = MetricsCollector(exporter=exporter)
        orch = _make_orchestrator()
        collector.set_orchestrators({"new_bot": orch})
        assert "new_bot" in collector.orchestrators


# =============================================================================
# Collection Tests
# =============================================================================


class TestCollectAll:
    """Tests for metric collection."""

    async def test_collect_all_basic(self, collector):
        await collector.collect_all()
        metrics = collector.exporter.metrics
        # Should have strategy_active metric
        assert "traderagent_strategy_active" in metrics

    async def test_collect_sets_health(self, collector):
        await collector.collect_all()
        metrics = collector.exporter.metrics
        assert "traderagent_health_status" in metrics

    async def test_collect_sets_portfolio_value(self, collector):
        await collector.collect_all()
        metrics = collector.exporter.metrics
        assert "traderagent_portfolio_value" in metrics
        # Find the metric with bot label
        values = metrics["traderagent_portfolio_value"]
        assert any(v.labels.get("bot") == "test_bot" for v in values)

    async def test_collect_with_grid_status(self, exporter):
        orch = _make_orchestrator()
        orch.get_status = AsyncMock(
            return_value={
                "bot_name": "grid_bot",
                "state": "running",
                "current_price": "50000",
                "strategy_registry": {"total": 1, "active": 1},
                "health": {"overall_status": "healthy"},
                "grid": {
                    "active_orders": 10,
                    "total_profit": "250.5",
                },
            }
        )
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"grid_bot": orch},
        )
        await collector.collect_all()
        metrics = exporter.metrics
        assert "traderagent_grid_open_orders" in metrics
        assert "traderagent_pnl_total" in metrics

    async def test_collect_with_dca_status(self, exporter):
        orch = _make_orchestrator()
        orch.get_status = AsyncMock(
            return_value={
                "bot_name": "dca_bot",
                "state": "running",
                "current_price": "3000",
                "strategy_registry": {"total": 1, "active": 1},
                "health": {"overall_status": "healthy"},
                "dca": {"has_position": True, "current_step": 3, "max_steps": 10},
            }
        )
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"dca_bot": orch},
        )
        await collector.collect_all()
        metrics = exporter.metrics
        assert "traderagent_active_deals" in metrics

    async def test_collect_with_trend_follower(self, exporter):
        orch = _make_orchestrator()
        orch.get_status = AsyncMock(
            return_value={
                "bot_name": "tf_bot",
                "state": "running",
                "current_price": "50000",
                "strategy_registry": {"total": 1, "active": 1},
                "health": {"overall_status": "healthy"},
                "trend_follower": {
                    "active_positions": 2,
                    "statistics": {
                        "total_trades": 15,
                        "win_rate": 0.6,
                        "total_pnl": 1200.5,
                    },
                },
            }
        )
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"tf_bot": orch},
        )
        await collector.collect_all()
        metrics = exporter.metrics
        assert "traderagent_total_trades" in metrics

    async def test_collect_with_risk(self, exporter):
        orch = _make_orchestrator()
        orch.get_status = AsyncMock(
            return_value={
                "bot_name": "risk_bot",
                "state": "running",
                "current_price": "50000",
                "strategy_registry": {"total": 1, "active": 1},
                "health": {"overall_status": "healthy"},
                "risk": {"drawdown": Decimal("0.05"), "pnl_percentage": Decimal("0.12")},
            }
        )
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"risk_bot": orch},
        )
        await collector.collect_all()
        metrics = exporter.metrics
        assert "traderagent_pnl_unrealized" in metrics

    async def test_collect_handles_failed_bot(self, exporter):
        orch = _make_orchestrator()
        orch.get_status = AsyncMock(side_effect=RuntimeError("connection lost"))
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"failing_bot": orch},
        )
        # Should not raise
        await collector.collect_all()

    async def test_collect_stopped_bot(self, exporter):
        orch = _make_orchestrator(state="stopped")
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"stopped_bot": orch},
        )
        await collector.collect_all()
        metrics = exporter.metrics
        values = metrics["traderagent_strategy_active"]
        bot_metric = next(v for v in values if v.labels.get("bot") == "stopped_bot")
        assert bot_metric.value == 0.0

    async def test_collect_multiple_bots(self, exporter):
        orch1 = _make_orchestrator("bot1")
        orch2 = _make_orchestrator("bot2", state="paused")
        collector = MetricsCollector(
            exporter=exporter,
            orchestrators={"bot1": orch1, "bot2": orch2},
        )
        await collector.collect_all()
        metrics = exporter.metrics
        # Both bots should have strategy_active metrics
        values = metrics["traderagent_strategy_active"]
        bot_names = {v.labels.get("bot") for v in values}
        assert "bot1" in bot_names
        assert "bot2" in bot_names


# =============================================================================
# Manual Update Tests
# =============================================================================


class TestManualUpdates:
    """Tests for event-driven metric updates."""

    def test_record_trade(self, collector):
        collector.record_trade("test_bot", "grid")
        metrics = collector.exporter.metrics
        assert "traderagent_total_trades" in metrics

    def test_record_api_latency(self, collector):
        collector.record_api_latency("test_bot", 0.25)
        metrics = collector.exporter.metrics
        assert "traderagent_api_latency_seconds" in metrics
        values = metrics["traderagent_api_latency_seconds"]
        assert values[0].value == 0.25

    def test_record_regime_change(self, collector):
        collector.record_regime_change("test_bot")
        metrics = collector.exporter.metrics
        assert "traderagent_regime_changes_total" in metrics

    def test_record_safety_order(self, collector):
        collector.record_safety_order("test_bot")
        collector.record_safety_order("test_bot")
        metrics = collector.exporter.metrics
        values = metrics["traderagent_dca_safety_orders_filled"]
        assert values[0].value == 2.0


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestLifecycle:
    """Tests for start/stop lifecycle."""

    async def test_start_stop(self, collector):
        await collector.start()
        assert collector._running is True
        assert collector._task is not None
        await collector.stop()
        assert collector._running is False
        assert collector._task is None

    async def test_start_idempotent(self, collector):
        await collector.start()
        task1 = collector._task
        await collector.start()  # Second start should be no-op
        assert collector._task is task1
        await collector.stop()

    async def test_stop_without_start(self, collector):
        await collector.stop()  # Should not raise


# =============================================================================
# Status Tests
# =============================================================================


class TestStatus:
    """Tests for status reporting."""

    def test_get_status(self, collector):
        status = collector.get_status()
        assert status["running"] is False
        assert status["bot_count"] == 1
        assert "test_bot" in status["bot_names"]
        assert "exporter_status" in status

    async def test_get_status_running(self, collector):
        await collector.start()
        status = collector.get_status()
        assert status["running"] is True
        await collector.stop()
