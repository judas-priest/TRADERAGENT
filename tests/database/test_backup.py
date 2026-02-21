"""Tests for BackupManager — database backup and restore utilities."""

from datetime import datetime, timezone
from pathlib import Path

from bot.database.backup import (
    BackupInfo,
    BackupManager,
    parse_database_url,
)

# =============================================================================
# BackupInfo Tests
# =============================================================================


class TestBackupInfo:
    """Tests for BackupInfo dataclass."""

    def test_basic_creation(self, tmp_path):
        info = BackupInfo(
            file_path=tmp_path / "test.sql.gz",
            database_name="traderagent",
            label="pre-migration",
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            size_bytes=1024,
            compressed=True,
        )
        assert info.database_name == "traderagent"
        assert info.label == "pre-migration"
        assert info.compressed is True

    def test_to_dict(self, tmp_path):
        info = BackupInfo(
            file_path=tmp_path / "test.sql",
            database_name="testdb",
            label="manual",
            created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            size_bytes=2048,
            compressed=False,
        )
        d = info.to_dict()
        assert d["database_name"] == "testdb"
        assert d["label"] == "manual"
        assert d["size_bytes"] == 2048
        assert d["compressed"] is False
        assert "2025-06-01" in d["created_at"]
        assert str(tmp_path / "test.sql") == d["file_path"]

    def test_defaults(self, tmp_path):
        info = BackupInfo(
            file_path=tmp_path / "test.sql",
            database_name="db",
            label="test",
            created_at=datetime.now(timezone.utc),
        )
        assert info.size_bytes == 0
        assert info.compressed is False


# =============================================================================
# parse_database_url Tests
# =============================================================================


class TestParseDatabaseUrl:
    """Tests for URL parsing utility."""

    def test_full_asyncpg_url(self):
        result = parse_database_url("postgresql+asyncpg://user:pass@host:5432/dbname")
        assert result["host"] == "host"
        assert result["port"] == "5432"
        assert result["database"] == "dbname"
        assert result["username"] == "user"
        assert result["password"] == "pass"

    def test_plain_postgresql_url(self):
        result = parse_database_url("postgresql://admin:secret@db.example.com/mydb")
        assert result["host"] == "db.example.com"
        assert result["database"] == "mydb"
        assert result["username"] == "admin"
        assert result["password"] == "secret"

    def test_default_port(self):
        result = parse_database_url("postgresql://user:pass@host/db")
        assert result["port"] == "5432"

    def test_custom_port(self):
        result = parse_database_url("postgresql://user:pass@host:5433/db")
        assert result["port"] == "5433"

    def test_localhost_defaults(self):
        result = parse_database_url("postgresql://localhost/testdb")
        assert result["host"] == "localhost"
        assert result["username"] == ""
        assert result["password"] == ""


# =============================================================================
# BackupManager Init Tests
# =============================================================================


class TestBackupManagerInit:
    """Tests for BackupManager initialization."""

    def test_init_with_defaults(self):
        manager = BackupManager(database_url="postgresql+asyncpg://user:pass@host/db")
        assert manager.database_name == "db"
        assert manager.backup_dir == Path("backups")

    def test_init_with_custom_dir(self, tmp_path):
        backup_dir = tmp_path / "my_backups"
        manager = BackupManager(
            database_url="postgresql://localhost/test",
            backup_dir=backup_dir,
        )
        assert manager.backup_dir == backup_dir

    def test_database_name_property(self):
        manager = BackupManager(database_url="postgresql+asyncpg://user:pass@host/traderagent")
        assert manager.database_name == "traderagent"


# =============================================================================
# Filename Generation Tests
# =============================================================================


class TestFilenameGeneration:
    """Tests for backup filename generation."""

    def test_filename_format_compressed(self):
        manager = BackupManager(database_url="postgresql://localhost/testdb")
        filename = manager._generate_filename("pre-migration", compressed=True)
        assert filename.startswith("testdb_")
        assert filename.endswith("_pre-migration.sql.gz")

    def test_filename_format_uncompressed(self):
        manager = BackupManager(database_url="postgresql://localhost/testdb")
        filename = manager._generate_filename("snapshot", compressed=False)
        assert filename.endswith("_snapshot.sql")
        assert ".gz" not in filename

    def test_filename_sanitizes_label(self):
        manager = BackupManager(database_url="postgresql://localhost/db")
        filename = manager._generate_filename("my backup/test!")
        assert "/" not in filename
        assert "!" not in filename
        assert "my_backup_test_" in filename

    def test_filename_contains_timestamp(self):
        manager = BackupManager(database_url="postgresql://localhost/db")
        filename = manager._generate_filename("test")
        # Format: db_YYYYMMDD_HHMMSS_test.sql.gz
        parts = filename.split("_")
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS


# =============================================================================
# Backup Directory Tests
# =============================================================================


class TestBackupDirectory:
    """Tests for backup directory management."""

    def test_ensure_backup_dir_creates(self, tmp_path):
        backup_dir = tmp_path / "new_backups"
        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=backup_dir,
        )
        assert not backup_dir.exists()
        manager._ensure_backup_dir()
        assert backup_dir.exists()

    def test_ensure_backup_dir_existing(self, tmp_path):
        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        manager._ensure_backup_dir()  # Should not raise
        assert tmp_path.exists()


# =============================================================================
# List Backups Tests
# =============================================================================


class TestListBackups:
    """Tests for listing backups."""

    def test_list_empty_dir(self, tmp_path):
        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        assert manager.list_backups() == []

    def test_list_nonexistent_dir(self, tmp_path):
        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path / "nonexistent",
        )
        assert manager.list_backups() == []

    def test_list_backups_sorted_newest_first(self, tmp_path):
        # Create fake backup files
        (tmp_path / "db_20250101_120000_first.sql.gz").write_bytes(b"data1")
        (tmp_path / "db_20250201_120000_second.sql.gz").write_bytes(b"data2")
        (tmp_path / "db_20250301_120000_third.sql.gz").write_bytes(b"data3")

        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        backups = manager.list_backups()
        assert len(backups) == 3
        # Newest first (sorted by filename descending)
        assert "third" in backups[0].label
        assert "first" in backups[2].label

    def test_list_backups_includes_sql_files(self, tmp_path):
        (tmp_path / "db_20250101_120000_test.sql").write_bytes(b"sql data")
        (tmp_path / "db_20250102_120000_test.sql.gz").write_bytes(b"gz data")

        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        backups = manager.list_backups()
        assert len(backups) == 2

    def test_list_ignores_non_sql_files(self, tmp_path):
        (tmp_path / "readme.txt").write_bytes(b"not a backup")
        (tmp_path / "db_20250101_120000_test.sql.gz").write_bytes(b"backup")

        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        backups = manager.list_backups()
        assert len(backups) == 1


# =============================================================================
# Delete Backup Tests
# =============================================================================


class TestDeleteBackup:
    """Tests for deleting individual backups."""

    def test_delete_existing(self, tmp_path):
        backup_file = tmp_path / "test.sql.gz"
        backup_file.write_bytes(b"data")

        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        result = manager.delete_backup(backup_file)
        assert result is True
        assert not backup_file.exists()

    def test_delete_nonexistent(self, tmp_path):
        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        result = manager.delete_backup(tmp_path / "nonexistent.sql.gz")
        assert result is False


# =============================================================================
# Cleanup Tests
# =============================================================================


class TestCleanupBackups:
    """Tests for backup rotation/cleanup."""

    async def test_cleanup_removes_old(self, tmp_path):
        # Create 7 backup files
        for i in range(7):
            (tmp_path / f"db_202501{i+10:02d}_120000_backup{i}.sql.gz").write_bytes(b"data")

        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        removed = await manager.cleanup_old_backups(keep=3)
        assert removed == 4
        remaining = manager.list_backups()
        assert len(remaining) == 3

    async def test_cleanup_nothing_to_remove(self, tmp_path):
        (tmp_path / "db_20250101_120000_test.sql.gz").write_bytes(b"data")

        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        removed = await manager.cleanup_old_backups(keep=5)
        assert removed == 0

    async def test_cleanup_empty_dir(self, tmp_path):
        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        removed = await manager.cleanup_old_backups(keep=5)
        assert removed == 0


# =============================================================================
# Status Tests
# =============================================================================


class TestBackupManagerStatus:
    """Tests for status reporting."""

    def test_get_status_empty(self, tmp_path):
        manager = BackupManager(
            database_url="postgresql://localhost/testdb",
            backup_dir=tmp_path,
        )
        status = manager.get_status()
        assert status["database_name"] == "testdb"
        assert status["total_backups"] == 0
        assert status["total_size_bytes"] == 0
        assert status["latest_backup"] is None
        assert status["backup_dir_exists"] is True

    def test_get_status_with_backups(self, tmp_path):
        (tmp_path / "db_20250101_120000_test.sql.gz").write_bytes(b"x" * 100)
        (tmp_path / "db_20250102_120000_test.sql.gz").write_bytes(b"y" * 200)

        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path,
        )
        status = manager.get_status()
        assert status["total_backups"] == 2
        assert status["total_size_bytes"] == 300
        assert status["latest_backup"] is not None

    def test_get_status_nonexistent_dir(self, tmp_path):
        manager = BackupManager(
            database_url="postgresql://localhost/db",
            backup_dir=tmp_path / "nonexistent",
        )
        status = manager.get_status()
        assert status["backup_dir_exists"] is False
        assert status["total_backups"] == 0


# =============================================================================
# Tool Check Tests
# =============================================================================


class TestToolCheck:
    """Tests for checking CLI tool availability."""

    async def test_check_tools_returns_dict(self):
        manager = BackupManager(database_url="postgresql://localhost/db")
        result = await manager.check_tools_available()
        assert "pg_dump" in result
        assert "psql" in result
        assert isinstance(result["pg_dump"], bool)
        assert isinstance(result["psql"], bool)


# =============================================================================
# Build Env Tests
# =============================================================================


class TestBuildEnv:
    """Tests for environment variable construction."""

    def test_build_env_with_password(self):
        manager = BackupManager(database_url="postgresql://user:secret@host/db")
        env = manager._build_env()
        assert env["PGPASSWORD"] == "secret"

    def test_build_env_without_password(self):
        manager = BackupManager(database_url="postgresql://localhost/db")
        env = manager._build_env()
        assert env.get("PGPASSWORD", "") == ""
