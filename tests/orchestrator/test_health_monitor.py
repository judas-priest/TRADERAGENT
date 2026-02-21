"""Tests for HealthMonitor."""

from datetime import datetime, timedelta, timezone

import pytest

from bot.orchestrator.health_monitor import (
    HealthCheckResult,
    HealthMonitor,
    HealthStatus,
    HealthThresholds,
)
from bot.orchestrator.strategy_registry import (
    StrategyRegistry,
    StrategyState,
)


@pytest.fixture
def registry():
    """Create a fresh StrategyRegistry."""
    return StrategyRegistry(max_strategies=10)


@pytest.fixture
def monitor(registry):
    """Create a HealthMonitor with test-friendly thresholds."""
    thresholds = HealthThresholds(
        max_error_count=5,
        max_consecutive_errors=2,
        signal_timeout_seconds=60.0,
        trade_timeout_seconds=120.0,
        auto_restart=True,
        max_restart_attempts=2,
    )
    return HealthMonitor(
        registry=registry,
        thresholds=thresholds,
        check_interval=1.0,
    )


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_create_result(self):
        result = HealthCheckResult(
            strategy_id="test-1",
            status=HealthStatus.HEALTHY,
            message="OK",
        )
        assert result.strategy_id == "test-1"
        assert result.status == HealthStatus.HEALTHY
        assert result.timestamp is not None


class TestHealthMonitor:
    """Tests for HealthMonitor."""

    @pytest.mark.asyncio
    async def test_check_idle_strategy_is_healthy(self, registry, monitor):
        registry.register("s1", "grid")
        strategy = registry.get("s1")

        result = await monitor.check_strategy(strategy)
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_active_healthy_strategy(self, registry, monitor):
        registry.register("s1", "grid")
        await registry.start_strategy("s1")
        strategy = registry.get("s1")

        result = await monitor.check_strategy(strategy)
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_high_error_count(self, registry, monitor):
        registry.register("s1", "dca")
        await registry.start_strategy("s1")
        strategy = registry.get("s1")

        # Simulate many errors
        for i in range(6):
            strategy.record_error(f"Error {i}")

        result = await monitor.check_strategy(strategy)
        assert result.status == HealthStatus.UNHEALTHY
        assert "High error count" in result.message

    @pytest.mark.asyncio
    async def test_check_consecutive_errors_critical(self, registry, monitor):
        registry.register("s1", "smc")
        await registry.start_strategy("s1")
        strategy = registry.get("s1")

        # Record consecutive errors
        monitor.record_error("s1")
        monitor.record_error("s1")
        monitor.record_error("s1")

        result = await monitor.check_strategy(strategy)
        assert result.status == HealthStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_check_stale_signals_degraded(self, registry, monitor):
        registry.register("s1", "trend_follower")
        await registry.start_strategy("s1")
        strategy = registry.get("s1")

        # Set signal time to 2 minutes ago (threshold is 60s)
        strategy.metrics.last_signal_time = datetime.now(timezone.utc) - timedelta(seconds=120)

        result = await monitor.check_strategy(strategy)
        assert result.status == HealthStatus.DEGRADED
        assert "No signals" in result.message

    @pytest.mark.asyncio
    async def test_record_success_resets_consecutive(self, registry, monitor):
        registry.register("s1", "grid")
        await registry.start_strategy("s1")

        monitor.record_error("s1")
        monitor.record_error("s1")
        monitor.record_success("s1")

        strategy = registry.get("s1")
        result = await monitor.check_strategy(strategy)
        # Should NOT be critical since consecutive errors were reset
        assert result.status != HealthStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_check_all(self, registry, monitor):
        registry.register("s1", "grid")
        registry.register("s2", "dca")
        await registry.start_strategy("s1")

        results = await monitor.check_all()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_health_summary(self, registry, monitor):
        registry.register("s1", "grid")
        registry.register("s2", "dca")

        summary = monitor.get_health_summary()
        assert "overall" in summary
        assert "monitor_running" in summary
        assert summary["monitor_running"] is False

    @pytest.mark.asyncio
    async def test_start_stop_monitor(self, registry, monitor):
        registry.register("s1", "grid")

        await monitor.start()
        assert monitor._running is True

        await monitor.stop()
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_unhealthy_callback(self, registry, monitor):
        callback_called = {"called": False, "strategy_id": None}

        async def on_unhealthy(strategy_id, result):
            callback_called["called"] = True
            callback_called["strategy_id"] = strategy_id

        monitor.set_unhealthy_callback(on_unhealthy)
        registry.register("s1", "grid")
        await registry.start_strategy("s1")

        # Make strategy unhealthy
        strategy = registry.get("s1")
        for i in range(6):
            strategy.record_error(f"Error {i}")

        await monitor.check_all()
        assert callback_called["called"] is True
        assert callback_called["strategy_id"] == "s1"

    @pytest.mark.asyncio
    async def test_critical_callback(self, registry, monitor):
        callback_called = {"called": False}

        async def on_critical(strategy_id, result):
            callback_called["called"] = True

        monitor.set_critical_callback(on_critical)
        registry.register("s1", "smc")
        await registry.start_strategy("s1")

        # Make it critical
        monitor.record_error("s1")
        monitor.record_error("s1")
        monitor.record_error("s1")

        await monitor.check_all()
        assert callback_called["called"] is True

    @pytest.mark.asyncio
    async def test_auto_restart_on_error(self, registry, monitor):
        registry.register("s1", "grid")
        await registry.start_strategy("s1")
        strategy = registry.get("s1")

        # Put into ERROR state
        await strategy.transition_to(StrategyState.ERROR)
        assert strategy.state == StrategyState.ERROR

        # Check all should trigger auto-restart
        # First mark as critical with consecutive errors
        monitor.record_error("s1")
        monitor.record_error("s1")
        monitor.record_error("s1")

        await monitor.check_all()
        # Should have been restarted
        assert strategy.state == StrategyState.ACTIVE

    @pytest.mark.asyncio
    async def test_max_restart_attempts(self, registry, monitor):
        registry.register("s1", "grid")
        await registry.start_strategy("s1")
        strategy = registry.get("s1")

        # Exhaust restart attempts
        for _ in range(3):
            await strategy.transition_to(StrategyState.ERROR)
            monitor.record_error("s1")
            monitor.record_error("s1")
            monitor.record_error("s1")
            await monitor.check_all()

        # After 2 restarts (max), next should fail
        await strategy.transition_to(StrategyState.ERROR)
        monitor.record_error("s1")
        monitor.record_error("s1")
        monitor.record_error("s1")
        await monitor.check_all()
        # Strategy stays in ERROR (or previous state) - restart count exceeded
        assert monitor._restart_counts.get("s1", 0) <= 2
