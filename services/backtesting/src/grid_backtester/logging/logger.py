"""
Structured logging system with rotation and multiple log levels.
Uses structlog for structured logging with rich context.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import Processor


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path | None = None,
    log_to_console: bool = True,
    log_to_file: bool = True,
    json_logs: bool = False,
) -> None:
    """
    Configure the logging system.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (default: ./logs)
        log_to_console: Whether to log to console
        log_to_file: Whether to log to file
        json_logs: Whether to use JSON format for logs
    """
    if log_dir is None:
        log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    handlers = []

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level_int)
        handlers.append(console_handler)

    if log_to_file:
        app_log_file = log_dir / "backtester.log"
        file_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level_int)
        handlers.append(file_handler)

        error_log_file = log_dir / "error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        handlers.append(error_handler)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=log_to_console,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=log_level_int,
        handlers=handlers,
        force=True,
    )

    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance for a module."""
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""

    @property
    def logger(self) -> structlog.BoundLogger:
        return get_logger(self.__class__.__name__)


class log_context:
    """Context manager for adding context to logs."""

    def __init__(self, **kwargs: Any) -> None:
        self.context = kwargs

    def __enter__(self) -> None:
        structlog.contextvars.bind_contextvars(**self.context)

    def __exit__(self, *args: Any) -> None:
        structlog.contextvars.unbind_contextvars(*self.context.keys())
