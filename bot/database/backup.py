"""
BackupManager — Database backup and restore utilities.

Provides async-compatible backup/restore operations using pg_dump/pg_restore.
Supports backup rotation and metadata tracking.

Usage:
    manager = BackupManager(
        database_url="postgresql+asyncpg://user:pass@host/db",
        backup_dir="/backups",
    )
    backup = await manager.create_backup("pre-migration")
    await manager.restore_backup(backup.file_path)
    await manager.cleanup_old_backups(keep=5)
"""

import asyncio
import gzip
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bot.utils.logger import get_logger

logger = get_logger(__name__)

# Default backup directory
DEFAULT_BACKUP_DIR = Path("backups")


@dataclass
class BackupInfo:
    """Information about a single backup."""

    file_path: Path
    database_name: str
    label: str
    created_at: datetime
    size_bytes: int = 0
    compressed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "database_name": self.database_name,
            "label": self.label,
            "created_at": self.created_at.isoformat(),
            "size_bytes": self.size_bytes,
            "compressed": self.compressed,
        }


def parse_database_url(url: str) -> dict[str, str]:
    """
    Parse async database URL into connection components.

    Handles both postgresql+asyncpg:// and postgresql:// schemes.
    """
    # Replace asyncpg driver for parsing
    normalized = url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(normalized)

    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "database": (parsed.path or "/").lstrip("/"),
        "username": parsed.username or "",
        "password": parsed.password or "",
    }


class BackupManager:
    """
    Database backup and restore manager.

    Uses pg_dump/pg_restore for PostgreSQL backup operations.
    Supports compressed backups and automatic rotation.
    """

    def __init__(
        self,
        database_url: str,
        backup_dir: str | Path | None = None,
    ) -> None:
        self._database_url = database_url
        self._backup_dir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
        self._db_params = parse_database_url(database_url)

    @property
    def backup_dir(self) -> Path:
        return self._backup_dir

    @property
    def database_name(self) -> str:
        return self._db_params["database"]

    def _ensure_backup_dir(self) -> None:
        """Create backup directory if it doesn't exist."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _build_env(self) -> dict[str, str]:
        """Build environment dict with PGPASSWORD for pg_dump/pg_restore."""
        import os

        env = dict(os.environ)
        if self._db_params["password"]:
            env["PGPASSWORD"] = self._db_params["password"]
        return env

    def _generate_filename(self, label: str, compressed: bool = True) -> str:
        """Generate backup filename with timestamp and label."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        db_name = self._db_params["database"]
        ext = ".sql.gz" if compressed else ".sql"
        # Sanitize label
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        return f"{db_name}_{timestamp}_{safe_label}{ext}"

    # =========================================================================
    # Backup Operations
    # =========================================================================

    async def create_backup(
        self,
        label: str = "manual",
        compressed: bool = True,
    ) -> BackupInfo:
        """
        Create a database backup using pg_dump.

        Args:
            label: Descriptive label for the backup.
            compressed: Whether to gzip-compress the output.

        Returns:
            BackupInfo with details about the created backup.

        Raises:
            RuntimeError: If pg_dump fails.
        """
        self._ensure_backup_dir()

        filename = self._generate_filename(label, compressed)
        raw_path = (
            self._backup_dir / filename.replace(".gz", "")
            if compressed
            else self._backup_dir / filename
        )
        final_path = self._backup_dir / filename

        cmd = [
            "pg_dump",
            "-h",
            self._db_params["host"],
            "-p",
            self._db_params["port"],
            "-U",
            self._db_params["username"],
            "-d",
            self._db_params["database"],
            "--no-password",
            "-f",
            str(raw_path),
        ]

        logger.info(
            "backup_starting",
            database=self._db_params["database"],
            label=label,
            compressed=compressed,
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=self._build_env(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RuntimeError(f"pg_dump failed (exit {process.returncode}): {error_msg}")

            # Compress if requested
            if compressed and raw_path.exists():
                with open(raw_path, "rb") as f_in, gzip.open(final_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                raw_path.unlink()

            target = final_path if compressed else raw_path
            size = target.stat().st_size if target.exists() else 0

            info = BackupInfo(
                file_path=target,
                database_name=self._db_params["database"],
                label=label,
                created_at=datetime.now(timezone.utc),
                size_bytes=size,
                compressed=compressed,
            )

            logger.info(
                "backup_complete",
                file=str(target),
                size_bytes=size,
            )

            return info

        except FileNotFoundError:
            raise RuntimeError("pg_dump not found. Ensure PostgreSQL client tools are installed.")

    async def restore_backup(
        self,
        backup_path: str | Path,
    ) -> None:
        """
        Restore a database from a backup file.

        Args:
            backup_path: Path to the .sql or .sql.gz backup file.

        Raises:
            FileNotFoundError: If backup file doesn't exist.
            RuntimeError: If restore fails.
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        logger.info("restore_starting", file=str(backup_path))

        # Decompress if needed
        sql_path = backup_path
        temp_decompressed = False

        if backup_path.suffix == ".gz":
            sql_path = backup_path.with_suffix("")  # Remove .gz
            with gzip.open(backup_path, "rb") as f_in, open(sql_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            temp_decompressed = True

        try:
            cmd = [
                "psql",
                "-h",
                self._db_params["host"],
                "-p",
                self._db_params["port"],
                "-U",
                self._db_params["username"],
                "-d",
                self._db_params["database"],
                "--no-password",
                "-f",
                str(sql_path),
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=self._build_env(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RuntimeError(f"psql restore failed (exit {process.returncode}): {error_msg}")

            logger.info("restore_complete", file=str(backup_path))

        finally:
            # Clean up temp decompressed file
            if temp_decompressed and sql_path.exists():
                sql_path.unlink()

    # =========================================================================
    # Backup Management
    # =========================================================================

    def list_backups(self) -> list[BackupInfo]:
        """
        List all backups in the backup directory, sorted newest first.

        Returns:
            List of BackupInfo objects.
        """
        if not self._backup_dir.exists():
            return []

        backups = []
        for path in sorted(self._backup_dir.iterdir(), reverse=True):
            if path.suffix in (".sql", ".gz") and path.is_file():
                # Parse filename: dbname_YYYYMMDD_HHMMSS_label.sql[.gz]
                parts = path.stem.replace(".sql", "").split("_", 3)
                label = parts[3] if len(parts) > 3 else "unknown"

                try:
                    created_str = f"{parts[1]}_{parts[2]}" if len(parts) > 2 else ""
                    created = (
                        datetime.strptime(created_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
                        if created_str
                        else datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                    )
                except (ValueError, IndexError):
                    created = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

                backups.append(
                    BackupInfo(
                        file_path=path,
                        database_name=self._db_params["database"],
                        label=label,
                        created_at=created,
                        size_bytes=path.stat().st_size,
                        compressed=path.name.endswith(".gz"),
                    )
                )

        return backups

    async def cleanup_old_backups(self, keep: int = 5) -> int:
        """
        Remove old backups, keeping only the most recent ones.

        Args:
            keep: Number of recent backups to keep.

        Returns:
            Number of backups removed.
        """
        backups = self.list_backups()

        if len(backups) <= keep:
            return 0

        to_remove = backups[keep:]
        removed = 0

        for backup in to_remove:
            try:
                backup.file_path.unlink()
                removed += 1
                logger.info("backup_removed", file=str(backup.file_path))
            except OSError as e:
                logger.warning("backup_remove_failed", file=str(backup.file_path), error=str(e))

        logger.info("backup_cleanup_complete", removed=removed, kept=keep)
        return removed

    def delete_backup(self, backup_path: str | Path) -> bool:
        """
        Delete a specific backup file.

        Returns:
            True if deleted, False if file not found.
        """
        path = Path(backup_path)
        if path.exists():
            path.unlink()
            logger.info("backup_deleted", file=str(path))
            return True
        return False

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get backup manager status."""
        backups = self.list_backups()
        total_size = sum(b.size_bytes for b in backups)

        return {
            "backup_dir": str(self._backup_dir),
            "backup_dir_exists": self._backup_dir.exists(),
            "database_name": self._db_params["database"],
            "total_backups": len(backups),
            "total_size_bytes": total_size,
            "latest_backup": backups[0].to_dict() if backups else None,
        }

    async def check_tools_available(self) -> dict[str, bool]:
        """Check if required CLI tools (pg_dump, psql) are available."""
        tools = {}
        for tool in ("pg_dump", "psql"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    tool,
                    "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                tools[tool] = proc.returncode == 0
            except FileNotFoundError:
                tools[tool] = False
        return tools
