"""
Multi-bot orchestration load testing — StrategyRegistry lifecycle under load.

Tests real StrategyRegistry and StrategyInstance objects under concurrent pressure.
"""

import asyncio
import time
from decimal import Decimal

from bot.orchestrator.strategy_registry import StrategyInstance, StrategyRegistry, StrategyState


class TestMultiBotOrchestration:
    """Test orchestration components under load."""

    async def test_10_registries_concurrent_lifecycle(self):
        """10 StrategyRegistry instances × 10 strategies, full lifecycle concurrently."""

        async def full_lifecycle(registry_id: int):
            reg = StrategyRegistry(max_strategies=20)
            for s in range(10):
                sid = f"reg{registry_id}_strat{s}"
                reg.register(sid, "grid", {"param": s})
                assert await reg.start_strategy(sid)
                assert await reg.pause_strategy(sid)
                assert await reg.resume_strategy(sid)
                assert await reg.stop_strategy(sid)
            return reg.get_registry_status()

        start = time.perf_counter()
        results = await asyncio.gather(*[full_lifecycle(i) for i in range(10)])
        elapsed = time.perf_counter() - start

        assert len(results) == 10
        for status in results:
            assert status["total_strategies"] == 10
            # All should be in stopped state
            assert status["states"].get("stopped", 0) == 10
        assert elapsed < 5.0, f"10 registries lifecycle took {elapsed:.2f}s"
        print(f"\n  10 registries × 10 strategies lifecycle: {elapsed:.2f}s")

    async def test_registry_100_strategies(self):
        """Single registry with 100 strategies — register, start, stop."""
        reg = StrategyRegistry(max_strategies=200)

        start = time.perf_counter()
        # Register 100
        for i in range(100):
            reg.register(f"strat_{i}", ["grid", "dca", "smc", "trend"][i % 4])
        # Start all
        await asyncio.gather(*[reg.start_strategy(f"strat_{i}") for i in range(100)])
        # Stop all
        results = await reg.stop_all()
        elapsed = time.perf_counter() - start

        assert reg.strategy_count == 100
        assert len(reg.get_active()) == 0
        assert len(reg.get_by_state(StrategyState.STOPPED)) == 100
        assert elapsed < 2.0, f"100 strategies lifecycle took {elapsed:.2f}s"
        print(f"\n  100 strategies register+start+stop: {elapsed:.2f}s")

    async def test_concurrent_state_transitions_50(self):
        """50 concurrent start/pause/resume/stop transitions."""
        reg = StrategyRegistry(max_strategies=100)
        for i in range(50):
            reg.register(f"s_{i}", "grid")

        start = time.perf_counter()

        # Start all concurrently
        starts = await asyncio.gather(*[reg.start_strategy(f"s_{i}") for i in range(50)])
        assert all(starts)

        # Pause all concurrently
        pauses = await asyncio.gather(*[reg.pause_strategy(f"s_{i}") for i in range(50)])
        assert all(pauses)

        # Resume all concurrently
        resumes = await asyncio.gather(*[reg.resume_strategy(f"s_{i}") for i in range(50)])
        assert all(resumes)

        # Stop all concurrently
        stops = await asyncio.gather(*[reg.stop_strategy(f"s_{i}") for i in range(50)])
        assert all(stops)

        elapsed = time.perf_counter() - start

        assert len(reg.get_by_state(StrategyState.STOPPED)) == 50
        assert elapsed < 3.0, f"50 × 4 transitions took {elapsed:.2f}s"
        print(
            f"\n  50 strategies × 4 transitions: {elapsed:.2f}s ({200/elapsed:.0f} transitions/s)"
        )

    def test_metrics_recording_under_load(self):
        """1000 record_trade() + record_signal() calls on a single strategy."""
        instance = StrategyInstance(
            strategy_id="perf_test",
            strategy_type="grid",
            config={},
        )

        start = time.perf_counter()
        for i in range(1000):
            instance.record_signal()
            instance.record_trade(Decimal(str(i % 100 - 50)), profitable=(i % 3 != 0))
        elapsed = time.perf_counter() - start

        assert instance.metrics.total_signals == 1000
        assert instance.metrics.executed_trades == 1000
        assert elapsed < 1.0, f"1000 metric recordings took {elapsed:.2f}s"
        print(f"\n  1000 signal+trade recordings: {elapsed*1000:.1f}ms")

    async def test_orchestrator_status_aggregation(self, mock_orchestrators_10):
        """10 mock orchestrators, 100 concurrent get_status() calls."""

        async def get_all_statuses():
            return {name: orch.get_status() for name, orch in mock_orchestrators_10.items()}

        start = time.perf_counter()
        results = await asyncio.gather(*[get_all_statuses() for _ in range(100)])
        elapsed = time.perf_counter() - start

        assert len(results) == 100
        for r in results:
            assert len(r) == 10
            for name, status in r.items():
                assert status["bot_name"] == name
        assert elapsed < 3.0, f"100 × 10 status calls took {elapsed:.2f}s"
        print(f"\n  100 × 10 status aggregations: {elapsed:.2f}s ({1000/elapsed:.0f} calls/s)")
