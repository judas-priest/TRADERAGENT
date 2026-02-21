"""Tests for StrategyRegistry and StrategyInstance."""

from decimal import Decimal

import pytest

from bot.orchestrator.strategy_registry import (
    StrategyInstance,
    StrategyRegistry,
    StrategyState,
)

# =========================================================================
# StrategyInstance Tests
# =========================================================================


class TestStrategyInstance:
    """Tests for StrategyInstance state management."""

    def test_create_instance(self):
        instance = StrategyInstance(
            strategy_id="test-smc-1",
            strategy_type="smc",
            config={"ema_fast": 20},
        )
        assert instance.strategy_id == "test-smc-1"
        assert instance.strategy_type == "smc"
        assert instance.state == StrategyState.IDLE
        assert instance.started_at is None
        assert instance.stopped_at is None

    def test_valid_transitions(self):
        instance = StrategyInstance(
            strategy_id="test-1",
            strategy_type="grid",
            config={},
        )
        # IDLE can go to STARTING
        assert instance.can_transition_to(StrategyState.STARTING)
        # IDLE cannot go to ACTIVE directly
        assert not instance.can_transition_to(StrategyState.ACTIVE)
        assert not instance.can_transition_to(StrategyState.STOPPED)

    @pytest.mark.asyncio
    async def test_transition_idle_to_active(self):
        instance = StrategyInstance(
            strategy_id="test-1",
            strategy_type="dca",
            config={},
        )
        assert await instance.transition_to(StrategyState.STARTING)
        assert instance.state == StrategyState.STARTING

        assert await instance.transition_to(StrategyState.ACTIVE)
        assert instance.state == StrategyState.ACTIVE
        assert instance.started_at is not None

    @pytest.mark.asyncio
    async def test_invalid_transition_rejected(self):
        instance = StrategyInstance(
            strategy_id="test-1",
            strategy_type="grid",
            config={},
        )
        # Can't go directly from IDLE to STOPPED
        assert not await instance.transition_to(StrategyState.STOPPED)
        assert instance.state == StrategyState.IDLE

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        instance = StrategyInstance(
            strategy_id="lifecycle-test",
            strategy_type="smc",
            config={},
        )
        # IDLE → STARTING → ACTIVE → PAUSED → ACTIVE → STOPPING → STOPPED → IDLE
        assert await instance.transition_to(StrategyState.STARTING)
        assert await instance.transition_to(StrategyState.ACTIVE)
        assert await instance.transition_to(StrategyState.PAUSED)
        assert await instance.transition_to(StrategyState.ACTIVE)
        assert await instance.transition_to(StrategyState.STOPPING)
        assert await instance.transition_to(StrategyState.STOPPED)
        assert instance.stopped_at is not None
        assert instance.metrics.uptime_seconds >= 0
        # Can reset
        assert await instance.transition_to(StrategyState.IDLE)

    @pytest.mark.asyncio
    async def test_error_state_transition(self):
        instance = StrategyInstance(
            strategy_id="error-test",
            strategy_type="grid",
            config={},
        )
        await instance.transition_to(StrategyState.STARTING)
        await instance.transition_to(StrategyState.ACTIVE)

        # ACTIVE → ERROR
        assert await instance.transition_to(StrategyState.ERROR)
        assert instance.state == StrategyState.ERROR

        # ERROR → IDLE (reset)
        assert await instance.transition_to(StrategyState.IDLE)
        assert instance.state == StrategyState.IDLE

    def test_record_error(self):
        instance = StrategyInstance(
            strategy_id="test-1",
            strategy_type="grid",
            config={},
        )
        instance.record_error("Connection timeout")
        assert instance.metrics.error_count == 1
        assert instance.metrics.last_error == "Connection timeout"
        assert instance.metrics.last_error_time is not None

    def test_record_signal(self):
        instance = StrategyInstance(
            strategy_id="test-1",
            strategy_type="smc",
            config={},
        )
        instance.record_signal()
        instance.record_signal()
        assert instance.metrics.total_signals == 2
        assert instance.metrics.last_signal_time is not None

    def test_record_trade(self):
        instance = StrategyInstance(
            strategy_id="test-1",
            strategy_type="trend_follower",
            config={},
        )
        instance.record_trade(Decimal("150"), profitable=True)
        instance.record_trade(Decimal("-50"), profitable=False)
        instance.record_trade(Decimal("200"), profitable=True)

        assert instance.metrics.executed_trades == 3
        assert instance.metrics.profitable_trades == 2
        assert instance.metrics.total_pnl == Decimal("300")

    def test_get_status(self):
        instance = StrategyInstance(
            strategy_id="status-test",
            strategy_type="dca",
            config={"max_steps": 5},
        )
        instance.record_trade(Decimal("100"), profitable=True)
        instance.record_trade(Decimal("-25"), profitable=False)

        status = instance.get_status()
        assert status["strategy_id"] == "status-test"
        assert status["strategy_type"] == "dca"
        assert status["state"] == "idle"
        assert status["metrics"]["executed_trades"] == 2
        assert status["metrics"]["win_rate"] == 0.5
        assert status["metrics"]["total_pnl"] == "75"


# =========================================================================
# StrategyRegistry Tests
# =========================================================================


class TestStrategyRegistry:
    """Tests for StrategyRegistry."""

    def test_register_strategy(self):
        registry = StrategyRegistry(max_strategies=5)
        instance = registry.register("smc-1", "smc", {"param": 1})

        assert instance.strategy_id == "smc-1"
        assert registry.strategy_count == 1

    def test_register_duplicate_raises(self):
        registry = StrategyRegistry()
        registry.register("smc-1", "smc")

        with pytest.raises(ValueError, match="already registered"):
            registry.register("smc-1", "smc")

    def test_register_max_limit(self):
        registry = StrategyRegistry(max_strategies=2)
        registry.register("s1", "grid")
        registry.register("s2", "dca")

        with pytest.raises(ValueError, match="Maximum strategies"):
            registry.register("s3", "smc")

    def test_unregister_idle_strategy(self):
        registry = StrategyRegistry()
        registry.register("s1", "grid")

        assert registry.unregister("s1")
        assert registry.strategy_count == 0

    @pytest.mark.asyncio
    async def test_unregister_active_strategy_fails(self):
        registry = StrategyRegistry()
        registry.register("s1", "grid")
        await registry.start_strategy("s1")

        assert not registry.unregister("s1")
        assert registry.strategy_count == 1

    def test_unregister_nonexistent(self):
        registry = StrategyRegistry()
        assert not registry.unregister("nonexistent")

    def test_get_by_type(self):
        registry = StrategyRegistry()
        registry.register("smc-1", "smc")
        registry.register("smc-2", "smc")
        registry.register("grid-1", "grid")

        smc_strategies = registry.get_by_type("smc")
        assert len(smc_strategies) == 2
        assert all(s.strategy_type == "smc" for s in smc_strategies)

    @pytest.mark.asyncio
    async def test_get_active(self):
        registry = StrategyRegistry()
        registry.register("s1", "grid")
        registry.register("s2", "dca")
        registry.register("s3", "smc")

        await registry.start_strategy("s1")
        await registry.start_strategy("s2")

        active = registry.get_active()
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_start_strategy(self):
        registry = StrategyRegistry()
        registry.register("s1", "grid")

        assert await registry.start_strategy("s1")
        instance = registry.get("s1")
        assert instance.state == StrategyState.ACTIVE

    @pytest.mark.asyncio
    async def test_start_nonexistent_strategy(self):
        registry = StrategyRegistry()
        assert not await registry.start_strategy("nonexistent")

    @pytest.mark.asyncio
    async def test_stop_strategy(self):
        registry = StrategyRegistry()
        registry.register("s1", "grid")
        await registry.start_strategy("s1")

        assert await registry.stop_strategy("s1")
        instance = registry.get("s1")
        assert instance.state == StrategyState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        registry = StrategyRegistry()
        registry.register("s1", "dca")
        await registry.start_strategy("s1")

        assert await registry.pause_strategy("s1")
        assert registry.get("s1").state == StrategyState.PAUSED

        assert await registry.resume_strategy("s1")
        assert registry.get("s1").state == StrategyState.ACTIVE

    @pytest.mark.asyncio
    async def test_reset_strategy(self):
        registry = StrategyRegistry()
        registry.register("s1", "smc")
        await registry.start_strategy("s1")
        await registry.stop_strategy("s1")

        assert await registry.reset_strategy("s1")
        assert registry.get("s1").state == StrategyState.IDLE

    @pytest.mark.asyncio
    async def test_stop_all(self):
        registry = StrategyRegistry()
        registry.register("s1", "grid")
        registry.register("s2", "dca")
        registry.register("s3", "smc")

        await registry.start_strategy("s1")
        await registry.start_strategy("s2")
        # s3 stays idle

        results = await registry.stop_all()
        assert results["s1"] is True
        assert results["s2"] is True
        assert "s3" not in results  # was idle, not stopped

    def test_get_registry_status(self):
        registry = StrategyRegistry(max_strategies=5)
        registry.register("s1", "grid")
        registry.register("s2", "dca")

        status = registry.get_registry_status()
        assert status["total_strategies"] == 2
        assert status["max_strategies"] == 5
        assert len(status["strategies"]) == 2

    @pytest.mark.asyncio
    async def test_get_by_state(self):
        registry = StrategyRegistry()
        registry.register("s1", "grid")
        registry.register("s2", "dca")
        registry.register("s3", "smc")

        await registry.start_strategy("s1")
        await registry.start_strategy("s2")
        await registry.pause_strategy("s2")

        active = registry.get_by_state(StrategyState.ACTIVE)
        assert len(active) == 1
        assert active[0].strategy_id == "s1"

        paused = registry.get_by_state(StrategyState.PAUSED)
        assert len(paused) == 1
        assert paused[0].strategy_id == "s2"

        idle = registry.get_by_state(StrategyState.IDLE)
        assert len(idle) == 1
        assert idle[0].strategy_id == "s3"
