"""Tests for MigrationRunner — programmatic Alembic migration management."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bot.database.migrations import (
    MigrationInfo,
    MigrationRunner,
    MigrationStatus,
    ALEMBIC_DIR,
    PROJECT_ROOT,
)


# =============================================================================
# MigrationInfo Tests
# =============================================================================


class TestMigrationInfo:
    """Tests for MigrationInfo dataclass."""

    def test_basic_creation(self):
        info = MigrationInfo(
            revision="abc123",
            down_revision="def456",
            description="Add users table",
        )
        assert info.revision == "abc123"
        assert info.down_revision == "def456"
        assert info.description == "Add users table"
        assert info.created_at is None

    def test_to_dict(self):
        info = MigrationInfo(
            revision="abc123",
            down_revision=None,
            description="Initial migration",
        )
        d = info.to_dict()
        assert d["revision"] == "abc123"
        assert d["down_revision"] is None
        assert d["description"] == "Initial migration"
        assert d["created_at"] is None

    def test_to_dict_with_datetime(self):
        from datetime import datetime, timezone

        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        info = MigrationInfo(
            revision="abc123",
            down_revision=None,
            description="test",
            created_at=dt,
        )
        d = info.to_dict()
        assert "2025-01-15" in d["created_at"]


# =============================================================================
# MigrationStatus Tests
# =============================================================================


class TestMigrationStatus:
    """Tests for MigrationStatus dataclass."""

    def test_basic_creation(self):
        status = MigrationStatus(
            current_revision="abc123",
            head_revision="abc123",
            is_up_to_date=True,
        )
        assert status.current_revision == "abc123"
        assert status.is_up_to_date is True
        assert status.pending_migrations == []
        assert status.applied_migrations == []

    def test_to_dict(self):
        info = MigrationInfo(revision="rev1", down_revision=None, description="test")
        status = MigrationStatus(
            current_revision="rev0",
            head_revision="rev1",
            is_up_to_date=False,
            pending_migrations=[info],
            applied_migrations=["rev0"],
        )
        d = status.to_dict()
        assert d["current_revision"] == "rev0"
        assert d["head_revision"] == "rev1"
        assert d["is_up_to_date"] is False
        assert d["pending_count"] == 1
        assert len(d["pending_migrations"]) == 1
        assert d["applied_migrations"] == ["rev0"]

    def test_empty_status(self):
        status = MigrationStatus(
            current_revision=None,
            head_revision=None,
            is_up_to_date=True,
        )
        d = status.to_dict()
        assert d["current_revision"] is None
        assert d["pending_count"] == 0


# =============================================================================
# MigrationRunner Tests
# =============================================================================


class TestMigrationRunnerInit:
    """Tests for MigrationRunner initialization."""

    def test_init_with_defaults(self):
        runner = MigrationRunner(database_url="postgresql+asyncpg://user:pass@host/db")
        assert runner._database_url == "postgresql+asyncpg://user:pass@host/db"
        assert runner._script_location == str(ALEMBIC_DIR)

    def test_init_with_custom_paths(self, tmp_path):
        ini_path = tmp_path / "alembic.ini"
        ini_path.touch()
        script_dir = tmp_path / "alembic"
        script_dir.mkdir()

        runner = MigrationRunner(
            database_url="postgresql://localhost/test",
            alembic_ini_path=ini_path,
            script_location=script_dir,
        )
        assert runner._alembic_ini == ini_path
        assert runner._script_location == str(script_dir)

    def test_config_sets_url(self):
        runner = MigrationRunner(database_url="postgresql://localhost/testdb")
        cfg = runner._config
        assert cfg.get_main_option("sqlalchemy.url") == "postgresql://localhost/testdb"

    def test_config_sets_script_location(self):
        runner = MigrationRunner(database_url="postgresql://localhost/testdb")
        cfg = runner._config
        assert cfg.get_main_option("script_location") == str(ALEMBIC_DIR)


class TestMigrationRunnerOperations:
    """Tests for MigrationRunner migration operations."""

    @patch("bot.database.migrations.command")
    def test_upgrade_calls_command(self, mock_command):
        runner = MigrationRunner(database_url="postgresql://localhost/test")
        runner.upgrade("head")
        mock_command.upgrade.assert_called_once_with(runner._config, "head")

    @patch("bot.database.migrations.command")
    def test_upgrade_default_revision(self, mock_command):
        runner = MigrationRunner(database_url="postgresql://localhost/test")
        runner.upgrade()
        mock_command.upgrade.assert_called_once_with(runner._config, "head")

    @patch("bot.database.migrations.command")
    def test_downgrade_calls_command(self, mock_command):
        runner = MigrationRunner(database_url="postgresql://localhost/test")
        runner.downgrade("-1")
        mock_command.downgrade.assert_called_once_with(runner._config, "-1")

    @patch("bot.database.migrations.command")
    def test_downgrade_default_revision(self, mock_command):
        runner = MigrationRunner(database_url="postgresql://localhost/test")
        runner.downgrade()
        mock_command.downgrade.assert_called_once_with(runner._config, "-1")

    @patch("bot.database.migrations.command")
    def test_stamp_calls_command(self, mock_command):
        runner = MigrationRunner(database_url="postgresql://localhost/test")
        runner.stamp("head")
        mock_command.stamp.assert_called_once_with(runner._config, "head")

    @patch("bot.database.migrations.command")
    def test_stamp_default_revision(self, mock_command):
        runner = MigrationRunner(database_url="postgresql://localhost/test")
        runner.stamp()
        mock_command.stamp.assert_called_once_with(runner._config, "head")


class TestMigrationRunnerStatus:
    """Tests for MigrationRunner status/query methods."""

    def test_check_connectivity_with_url(self):
        runner = MigrationRunner(database_url="postgresql://localhost/test")
        assert runner.check_connectivity() is True

    def test_check_connectivity_empty_url(self):
        runner = MigrationRunner(database_url="")
        assert runner.check_connectivity() is False

    def test_get_config_info(self):
        runner = MigrationRunner(database_url="postgresql://localhost/testdb")
        info = runner.get_config_info()
        assert "database_url" in info
        assert "alembic_ini" in info
        assert "script_location" in info
        assert isinstance(info["ini_exists"], bool)
        assert isinstance(info["script_dir_exists"], bool)

    def test_get_config_info_truncates_long_url(self):
        long_url = "postgresql+asyncpg://user:longpassword@host:5432/database_name"
        runner = MigrationRunner(database_url=long_url)
        info = runner.get_config_info()
        assert info["database_url"].endswith("...")
        assert len(info["database_url"]) <= 24  # 20 + "..."

    def test_get_config_info_short_url(self):
        short_url = "pg://host/db"
        runner = MigrationRunner(database_url=short_url)
        info = runner.get_config_info()
        assert info["database_url"] == short_url


class TestProjectPaths:
    """Tests for project path constants."""

    def test_project_root_exists(self):
        assert PROJECT_ROOT.exists()

    def test_alembic_dir_path(self):
        assert ALEMBIC_DIR == PROJECT_ROOT / "alembic"
