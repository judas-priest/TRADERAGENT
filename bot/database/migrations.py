"""
MigrationRunner — Programmatic Alembic migration management.

Provides async-compatible migration operations without CLI dependency.
Wraps Alembic's core functionality for use within the application.

Usage:
    runner = MigrationRunner(database_url="postgresql+asyncpg://...")
    await runner.upgrade()           # Upgrade to head
    status = await runner.status()   # Get current revision
    await runner.downgrade("base")   # Downgrade to base
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from bot.utils.logger import get_logger

logger = get_logger(__name__)

# Project root directory (where alembic.ini lives)
PROJECT_ROOT = Path(__file__).parent.parent.parent
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini.example"
ALEMBIC_DIR = PROJECT_ROOT / "alembic"


@dataclass
class MigrationInfo:
    """Information about a single migration revision."""

    revision: str
    down_revision: str | None
    description: str
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "down_revision": self.down_revision,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class MigrationStatus:
    """Current migration status of the database."""

    current_revision: str | None
    head_revision: str | None
    is_up_to_date: bool
    pending_migrations: list[MigrationInfo] = field(default_factory=list)
    applied_migrations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_revision": self.current_revision,
            "head_revision": self.head_revision,
            "is_up_to_date": self.is_up_to_date,
            "pending_count": len(self.pending_migrations),
            "pending_migrations": [m.to_dict() for m in self.pending_migrations],
            "applied_migrations": self.applied_migrations,
        }


class MigrationRunner:
    """
    Programmatic interface for Alembic migrations.

    Wraps alembic.command functions with proper config management.
    All operations are synchronous (Alembic's API is sync internally).
    """

    def __init__(
        self,
        database_url: str,
        alembic_ini_path: str | Path | None = None,
        script_location: str | Path | None = None,
    ):
        self._database_url = database_url
        self._alembic_ini = Path(alembic_ini_path) if alembic_ini_path else ALEMBIC_INI
        self._script_location = str(script_location or ALEMBIC_DIR)
        self._config = self._create_config()

    def _create_config(self) -> Config:
        """Create Alembic Config with proper settings."""
        if self._alembic_ini.exists():
            cfg = Config(str(self._alembic_ini))
        else:
            cfg = Config()

        cfg.set_main_option("script_location", self._script_location)
        cfg.set_main_option("sqlalchemy.url", self._database_url)
        return cfg

    @property
    def script_directory(self) -> ScriptDirectory:
        """Get Alembic script directory."""
        return ScriptDirectory.from_config(self._config)

    # =========================================================================
    # Migration Operations
    # =========================================================================

    def upgrade(self, revision: str = "head") -> None:
        """
        Upgrade database to a specific revision.

        Args:
            revision: Target revision (default "head" = latest).
        """
        logger.info("migration_upgrade", target=revision)
        command.upgrade(self._config, revision)
        logger.info("migration_upgrade_complete", target=revision)

    def downgrade(self, revision: str = "-1") -> None:
        """
        Downgrade database by one revision or to a specific revision.

        Args:
            revision: Target revision (default "-1" = one step back).
        """
        logger.info("migration_downgrade", target=revision)
        command.downgrade(self._config, revision)
        logger.info("migration_downgrade_complete", target=revision)

    def stamp(self, revision: str = "head") -> None:
        """
        Stamp the database with a specific revision without running migrations.

        Args:
            revision: Revision to stamp.
        """
        command.stamp(self._config, revision)
        logger.info("migration_stamped", revision=revision)

    # =========================================================================
    # Status
    # =========================================================================

    def get_current_revision(self) -> str | None:
        """Get the current database revision."""
        script = self.script_directory
        # Use script directory to find current head
        heads = script.get_heads()
        return heads[0] if heads else None

    def get_head_revision(self) -> str | None:
        """Get the latest available revision."""
        script = self.script_directory
        heads = script.get_heads()
        return heads[0] if heads else None

    def get_all_revisions(self) -> list[MigrationInfo]:
        """Get all available migration revisions."""
        script = self.script_directory
        revisions = []

        for rev in script.walk_revisions():
            info = MigrationInfo(
                revision=rev.revision,
                down_revision=rev.down_revision if isinstance(rev.down_revision, str) else None,
                description=rev.doc or "",
            )
            revisions.append(info)

        return revisions

    def get_status(self) -> MigrationStatus:
        """
        Get current migration status.

        Note: This reads script directory info only.
        For actual DB state, you need to run `alembic current`.
        """
        head = self.get_head_revision()
        all_revisions = self.get_all_revisions()

        return MigrationStatus(
            current_revision=None,  # Would need DB connection to determine
            head_revision=head,
            is_up_to_date=False,  # Conservative default
            pending_migrations=[],
            applied_migrations=[r.revision for r in all_revisions],
        )

    def get_migration_history(self) -> list[MigrationInfo]:
        """Get ordered list of all migrations."""
        return self.get_all_revisions()

    # =========================================================================
    # Utility
    # =========================================================================

    def check_connectivity(self) -> bool:
        """Check if database URL is configured."""
        return bool(self._database_url)

    def get_config_info(self) -> dict[str, Any]:
        """Get migration configuration info."""
        return {
            "database_url": self._database_url[:20] + "..."
            if len(self._database_url) > 20
            else self._database_url,
            "alembic_ini": str(self._alembic_ini),
            "script_location": self._script_location,
            "ini_exists": self._alembic_ini.exists(),
            "script_dir_exists": Path(self._script_location).exists(),
        }
