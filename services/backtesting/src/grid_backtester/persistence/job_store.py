"""
JobStore — SQLite-based persistence for backtest/optimization jobs (Issue #7).

Stores job metadata, status, config, and results in SQLite via aiosqlite.
Replaces in-memory dict for production use.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from grid_backtester.logging import get_logger

logger = get_logger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS backtest_jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL DEFAULT 'backtest',
    status TEXT NOT NULL DEFAULT 'pending',
    config_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_jobs_status ON backtest_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON backtest_jobs(created_at);
"""


class JobStore:
    """Async SQLite-backed job store for backtest and optimization jobs."""

    def __init__(self, db_path: str = "data/jobs.db") -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create database and tables."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(CREATE_TABLE_SQL)
        await self._db.executescript(CREATE_INDEX_SQL)
        await self._db.commit()
        logger.info("JobStore initialized", db_path=self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def create(
        self,
        job_type: str = "backtest",
        config: dict[str, Any] | None = None,
    ) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        await self._db.execute(
            """INSERT INTO backtest_jobs
               (job_id, job_type, status, config_json, created_at, updated_at)
               VALUES (?, ?, 'pending', ?, ?, ?)""",
            (job_id, job_type, json.dumps(config or {}), now, now),
        )
        await self._db.commit()

        logger.info("Job created", job_id=job_id, job_type=job_type)
        return job_id

    async def update_status(
        self,
        job_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Update job status and optionally set result or error."""
        now = datetime.now(timezone.utc).isoformat()

        if status == "running":
            await self._db.execute(
                """UPDATE backtest_jobs
                   SET status=?, started_at=?, updated_at=?
                   WHERE job_id=?""",
                (status, now, now, job_id),
            )
        elif status == "completed":
            await self._db.execute(
                """UPDATE backtest_jobs
                   SET status=?, result_json=?, completed_at=?, updated_at=?
                   WHERE job_id=?""",
                (status, json.dumps(result) if result else None, now, now, job_id),
            )
        elif status == "failed":
            await self._db.execute(
                """UPDATE backtest_jobs
                   SET status=?, error_message=?, completed_at=?, updated_at=?
                   WHERE job_id=?""",
                (status, error, now, now, job_id),
            )
        else:
            await self._db.execute(
                """UPDATE backtest_jobs
                   SET status=?, updated_at=?
                   WHERE job_id=?""",
                (status, now, job_id),
            )
        await self._db.commit()

        logger.debug("Job status updated", job_id=job_id, status=status)

    async def get(self, job_id: str) -> dict[str, Any] | None:
        """Get a job by ID."""
        async with self._db.execute(
            "SELECT * FROM backtest_jobs WHERE job_id=?", (job_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    async def list_jobs(
        self,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List jobs with optional filters."""
        conditions = []
        params: list[Any] = []

        if status:
            conditions.append("status=?")
            params.append(status)
        if job_type:
            conditions.append("job_type=?")
            params.append(job_type)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        async with self._db.execute(
            f"SELECT * FROM backtest_jobs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    async def delete(self, job_id: str) -> bool:
        """Delete a job by ID."""
        cursor = await self._db.execute(
            "DELETE FROM backtest_jobs WHERE job_id=?", (job_id,)
        )
        await self._db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Job deleted", job_id=job_id)
        return deleted

    async def cleanup_old(self, max_age_days: int = 30) -> int:
        """Delete jobs older than max_age_days."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        cursor = await self._db.execute(
            "DELETE FROM backtest_jobs WHERE created_at < ? AND status IN ('completed', 'failed')",
            (cutoff,),
        )
        await self._db.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info("Old jobs cleaned up", deleted=deleted, max_age_days=max_age_days)
        return deleted

    async def count(self, status: str | None = None) -> int:
        """Count jobs with optional status filter."""
        if status:
            async with self._db.execute(
                "SELECT COUNT(*) FROM backtest_jobs WHERE status=?", (status,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]
        else:
            async with self._db.execute(
                "SELECT COUNT(*) FROM backtest_jobs"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        d = dict(row)
        if d.get("config_json"):
            d["config"] = json.loads(d.pop("config_json"))
        if d.get("result_json"):
            d["result"] = json.loads(d.pop("result_json"))
        else:
            d.pop("result_json", None)
        return d
