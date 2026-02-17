"""
Backtesting load testing — concurrent job submissions and polling.

Tests the async backtest job system (module-level _jobs dict, _semaphore(2)).
"""

import asyncio
import time

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def reset_backtest_state():
    """Clear backtest jobs between tests."""
    from web.backend.api.v1 import backtesting
    backtesting._jobs.clear()
    yield
    backtesting._jobs.clear()


def _backtest_payload(i: int = 0) -> dict:
    """Generate backtest run request payload."""
    return {
        "strategy_type": "grid",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-06-01T00:00:00Z",
        "initial_balance": "10000",
        "config": {"index": i},
    }


class TestBacktestingUnderLoad:
    """Test backtesting API under concurrent load."""

    async def test_10_concurrent_submissions(self, auth_client: AsyncClient):
        """Submit 10 backtest jobs concurrently — all should get 202."""
        start = time.perf_counter()
        responses = await asyncio.gather(
            *[auth_client.post("/api/v1/backtesting/run", json=_backtest_payload(i)) for i in range(10)]
        )
        elapsed = time.perf_counter() - start

        job_ids = set()
        for resp in responses:
            assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["status"] in ("pending", "running")
            job_ids.add(data["job_id"])

        assert len(job_ids) == 10, f"Expected 10 unique job_ids, got {len(job_ids)}"
        assert elapsed < 5.0, f"10 submissions took {elapsed:.2f}s"
        print(f"\n  10 concurrent submissions: {elapsed:.2f}s")

    async def test_semaphore_limits_concurrency(self, auth_client: AsyncClient):
        """5 jobs with semaphore(2) — verify max 2 run simultaneously."""
        from unittest.mock import patch
        import time as time_mod

        concurrent_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        original_run = None

        def tracked_run(data):
            nonlocal concurrent_count, max_concurrent
            # Use a threading-compatible approach
            import threading
            with threading.Lock():
                concurrent_count += 1
                if concurrent_count > max_concurrent:
                    max_concurrent = concurrent_count
            time_mod.sleep(0.3)  # Longer sleep to overlap
            with threading.Lock():
                concurrent_count -= 1
            return {"total_return_pct": 10.0, "sharpe_ratio": 1.0}

        with patch("web.backend.api.v1.backtesting._run_grid_backtest_offline", side_effect=tracked_run):
            responses = await asyncio.gather(
                *[auth_client.post("/api/v1/backtesting/run", json=_backtest_payload(i)) for i in range(5)]
            )

        # Wait for background tasks to complete
        await asyncio.sleep(2.0)

        assert all(r.status_code == 202 for r in responses)
        assert max_concurrent <= 2, f"Max concurrent was {max_concurrent}, expected ≤2"
        print(f"\n  Semaphore test: max concurrent = {max_concurrent} (limit=2)")

    async def test_status_polling_100(self, auth_client: AsyncClient):
        """Submit 1 job, poll status 100 times concurrently."""
        resp = await auth_client.post("/api/v1/backtesting/run", json=_backtest_payload())
        job_id = resp.json()["job_id"]

        start = time.perf_counter()
        responses = await asyncio.gather(
            *[auth_client.get(f"/api/v1/backtesting/{job_id}") for _ in range(100)]
        )
        elapsed = time.perf_counter() - start

        assert all(r.status_code == 200 for r in responses)
        for r in responses:
            data = r.json()
            assert data["job_id"] == job_id
            assert data["status"] in ("pending", "running", "completed")
        assert elapsed < 3.0, f"100 polls took {elapsed:.2f}s"
        print(f"\n  100 concurrent status polls: {elapsed:.2f}s")

    async def test_history_after_20_jobs(self, auth_client: AsyncClient):
        """Submit 20 jobs, wait, then GET /history."""
        for i in range(20):
            resp = await auth_client.post("/api/v1/backtesting/run", json=_backtest_payload(i))
            assert resp.status_code == 202

        # Wait for all jobs to complete (each takes 0.1s, max 2 concurrent → ~1s)
        await asyncio.sleep(2.0)

        start = time.perf_counter()
        resp = await auth_client.get("/api/v1/backtesting/history")
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 20, f"Expected 20 jobs, got {len(jobs)}"

        completed = [j for j in jobs if j["status"] == "completed"]
        print(f"\n  20 jobs history: {elapsed*1000:.1f}ms, {len(completed)}/20 completed")
