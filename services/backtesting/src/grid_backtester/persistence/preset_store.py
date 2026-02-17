"""
PresetStore — SQLite-backed preset storage for grid configurations (Issue #12).

Stores optimized grid presets per symbol/cluster for retrieval by the main bot.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from grid_backtester.logging import get_logger

logger = get_logger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS presets (
    preset_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    cluster TEXT NOT NULL DEFAULT '',
    config_yaml TEXT NOT NULL,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_presets_symbol ON presets(symbol);
CREATE INDEX IF NOT EXISTS idx_presets_active ON presets(is_active);
"""


class PresetStore:
    """Async SQLite-backed store for grid presets."""

    def __init__(self, db_path: str = "data/presets.db") -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create database and tables."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(CREATE_TABLE_SQL)
        await self._db.executescript(CREATE_INDEX_SQL)
        await self._db.commit()
        logger.info("PresetStore initialized", db_path=self.db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def create(
        self,
        symbol: str,
        config_yaml: str,
        cluster: str = "",
        metrics: dict[str, Any] | None = None,
    ) -> str:
        """Create a new preset, deactivating existing presets for the same symbol."""
        preset_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        # Deactivate existing presets for this symbol
        await self._db.execute(
            "UPDATE presets SET is_active=0, updated_at=? WHERE symbol=? AND is_active=1",
            (now, symbol),
        )

        await self._db.execute(
            """INSERT INTO presets
               (preset_id, symbol, cluster, config_yaml, metrics_json, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
            (preset_id, symbol, cluster, config_yaml, json.dumps(metrics or {}), now, now),
        )
        await self._db.commit()

        logger.info("Preset created", preset_id=preset_id, symbol=symbol)
        return preset_id

    async def get_by_symbol(self, symbol: str, active_only: bool = True) -> dict[str, Any] | None:
        """Get the active preset for a symbol."""
        query = "SELECT * FROM presets WHERE symbol=?"
        params: list[Any] = [symbol]
        if active_only:
            query += " AND is_active=1"
        query += " ORDER BY created_at DESC LIMIT 1"

        async with self._db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    async def get(self, preset_id: str) -> dict[str, Any] | None:
        """Get a preset by ID."""
        async with self._db.execute(
            "SELECT * FROM presets WHERE preset_id=?", (preset_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    async def list_presets(
        self,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List all presets."""
        query = "SELECT * FROM presets"
        if active_only:
            query += " WHERE is_active=1"
        query += " ORDER BY symbol ASC, created_at DESC LIMIT ?"

        async with self._db.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    async def update(
        self,
        preset_id: str,
        config_yaml: str | None = None,
        metrics: dict[str, Any] | None = None,
        is_active: bool | None = None,
    ) -> bool:
        """Update a preset."""
        now = datetime.now(timezone.utc).isoformat()
        sets = ["updated_at=?"]
        params: list[Any] = [now]

        if config_yaml is not None:
            sets.append("config_yaml=?")
            params.append(config_yaml)
        if metrics is not None:
            sets.append("metrics_json=?")
            params.append(json.dumps(metrics))
        if is_active is not None:
            sets.append("is_active=?")
            params.append(1 if is_active else 0)

        params.append(preset_id)
        cursor = await self._db.execute(
            f"UPDATE presets SET {', '.join(sets)} WHERE preset_id=?",
            params,
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete(self, preset_id: str) -> bool:
        """Delete a preset."""
        cursor = await self._db.execute(
            "DELETE FROM presets WHERE preset_id=?", (preset_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete_by_symbol(self, symbol: str) -> int:
        """Delete all presets for a symbol."""
        cursor = await self._db.execute(
            "DELETE FROM presets WHERE symbol=?", (symbol,)
        )
        await self._db.commit()
        return cursor.rowcount

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        d = dict(row)
        if d.get("metrics_json"):
            d["metrics"] = json.loads(d.pop("metrics_json"))
        else:
            d.pop("metrics_json", None)
        d["is_active"] = bool(d.get("is_active", 0))
        return d
