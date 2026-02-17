"""Tests for JobStore — async SQLite persistence."""

import os
import tempfile

import pytest
import pytest_asyncio

from grid_backtester.persistence.job_store import JobStore


@pytest_asyncio.fixture
async def job_store():
    """Create a temporary job store for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = JobStore(db_path=db_path)
    await store.initialize()
    yield store
    await store.close()
    os.unlink(db_path)


@pytest.mark.asyncio
class TestJobStore:

    async def test_create_returns_job_id(self, job_store):
        job_id = await job_store.create(job_type="backtest", config={"symbol": "BTCUSDT"})
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    async def test_get_returns_job(self, job_store):
        job_id = await job_store.create(job_type="backtest", config={"symbol": "ETHUSDT"})
        job = await job_store.get(job_id)
        assert job is not None
        assert job["job_id"] == job_id
        assert job["status"] == "pending"
        assert job["config"]["symbol"] == "ETHUSDT"

    async def test_get_nonexistent_returns_none(self, job_store):
        result = await job_store.get("nonexistent-id")
        assert result is None

    async def test_update_status_to_running(self, job_store):
        job_id = await job_store.create()
        await job_store.update_status(job_id, "running")
        job = await job_store.get(job_id)
        assert job["status"] == "running"
        assert job.get("started_at") is not None

    async def test_update_status_to_completed(self, job_store):
        job_id = await job_store.create()
        await job_store.update_status(job_id, "running")
        await job_store.update_status(job_id, "completed", result={"roi": 5.0})
        job = await job_store.get(job_id)
        assert job["status"] == "completed"
        assert job["result"]["roi"] == 5.0
        assert job.get("completed_at") is not None

    async def test_update_status_to_failed(self, job_store):
        job_id = await job_store.create()
        await job_store.update_status(job_id, "failed", error="boom")
        job = await job_store.get(job_id)
        assert job["status"] == "failed"
        assert job["error_message"] == "boom"

    async def test_list_jobs(self, job_store):
        await job_store.create(job_type="backtest")
        await job_store.create(job_type="optimize")

        jobs = await job_store.list_jobs()
        assert len(jobs) == 2

    async def test_list_jobs_with_status_filter(self, job_store):
        id1 = await job_store.create()
        id2 = await job_store.create()
        await job_store.update_status(id1, "running")

        running = await job_store.list_jobs(status="running")
        assert len(running) == 1
        assert running[0]["job_id"] == id1

    async def test_delete_job(self, job_store):
        job_id = await job_store.create()
        deleted = await job_store.delete(job_id)
        assert deleted is True

        job = await job_store.get(job_id)
        assert job is None

    async def test_delete_nonexistent_returns_false(self, job_store):
        deleted = await job_store.delete("no-such-id")
        assert deleted is False

    async def test_cleanup_old(self, job_store):
        job_id = await job_store.create()
        await job_store.update_status(job_id, "completed", result={})
        # With max_age_days=0, everything should be cleaned
        # But since we just created it, it won't be older than 0 days effectively
        deleted = await job_store.cleanup_old(max_age_days=30)
        # Should be 0 since the job was just created
        assert deleted == 0

    async def test_count(self, job_store):
        await job_store.create()
        await job_store.create()

        total = await job_store.count()
        assert total == 2

    async def test_count_with_status(self, job_store):
        id1 = await job_store.create()
        await job_store.create()
        await job_store.update_status(id1, "running")

        pending = await job_store.count(status="pending")
        assert pending == 1
        running = await job_store.count(status="running")
        assert running == 1
