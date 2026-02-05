"""Tests for logging system"""

from pathlib import Path

import structlog

from bot.utils.logger import LoggerMixin, get_logger, log_context, setup_logging


class TestLogger:
    """Test logging functionality"""

    def test_get_logger(self):
        """Test getting a logger"""
        logger = get_logger("test")
        assert logger is not None
        assert isinstance(logger, structlog.BoundLogger)

    def test_logger_mixin(self):
        """Test LoggerMixin"""

        class TestClass(LoggerMixin):
            pass

        obj = TestClass()
        assert hasattr(obj, "logger")
        assert isinstance(obj.logger, structlog.BoundLogger)

    def test_log_context(self):
        """Test log context manager"""
        logger = get_logger("test")

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
