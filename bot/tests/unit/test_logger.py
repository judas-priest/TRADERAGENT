"""Tests for logging system"""

from pathlib import Path

import structlog

from bot.utils.logger import LoggerMixin, get_logger, log_context, setup_logging


class TestLogger:
    """Test logging functionality"""

    def test_get_logger(self, tmp_path: Path):
        """Test getting a logger"""
        # Setup logging first to configure structlog
        setup_logging(
            log_level="INFO",
            log_dir=tmp_path / "logs",
            log_to_console=False,
            log_to_file=False,
        )
        logger = get_logger("test")
        assert logger is not None
        # After setup_logging, we get a proper logger (not just a proxy)
        assert hasattr(logger, "info")

    def test_logger_mixin(self, tmp_path: Path):
        """Test LoggerMixin"""
        # Setup logging first to configure structlog
        setup_logging(
            log_level="INFO",
            log_dir=tmp_path / "logs",
            log_to_console=False,
            log_to_file=False,
        )

        class TestClass(LoggerMixin):
            pass

        obj = TestClass()
        assert hasattr(obj, "logger")
        # After setup_logging, we get a proper logger
        assert hasattr(obj.logger, "info")

    def test_log_context(self):
        """Test log context manager"""
        get_logger("test")

        with log_context(user_id=123, action="test"):
            # Context should be bound here
            pass
        # Context should be unbound here

    def test_setup_logging(self, tmp_path: Path):
        """Test logging setup"""
        log_dir = tmp_path / "logs"
        setup_logging(
            log_level="DEBUG",
            log_dir=log_dir,
            log_to_console=False,
            log_to_file=True,
        )

        # Verify log directory created
        assert log_dir.exists()

        # Test logging
        logger = get_logger("test_setup")
        logger.info("test message")

        # Verify log file created
        assert (log_dir / "bot.log").exists()
