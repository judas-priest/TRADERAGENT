"""
FastAPI application factory for grid backtesting service (Issue #9).

Provides REST API for:
- Running backtests and optimizations
- Managing presets
- Viewing charts
- Health checks
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI

from grid_backtester.caching.indicator_cache import IndicatorCache
from grid_backtester.logging import setup_logging, get_logger
from grid_backtester.persistence.checkpoint import OptimizationCheckpoint
from grid_backtester.persistence.job_store import JobStore
from grid_backtester.persistence.preset_store import PresetStore

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — initialize and cleanup resources."""
    # Setup logging
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    json_logs = os.environ.get("JSON_LOGS", "false").lower() == "true"
    setup_logging(
        log_level=log_level,
        json_logs=json_logs,
        log_to_file=True,
        log_dir=Path(os.environ.get("LOG_DIR", "logs")),
    )

    # Create data directory
    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    # Initialize stores
    jobs_db = os.environ.get("JOBS_DB_PATH", str(data_dir / "jobs.db"))
    presets_db = os.environ.get("PRESETS_DB_PATH", str(data_dir / "presets.db"))

    job_store = JobStore(db_path=jobs_db)
    preset_store = PresetStore(db_path=presets_db)

    await job_store.initialize()
    await preset_store.initialize()

    # Initialize indicator cache and optimization checkpoint
    indicator_cache = IndicatorCache()
    checkpoint = OptimizationCheckpoint(checkpoint_dir=str(data_dir / "checkpoints"))

    app.state.job_store = job_store
    app.state.preset_store = preset_store
    app.state.indicator_cache = indicator_cache
    app.state.checkpoint = checkpoint

    # Check plotly availability for chart generation
    try:
        import plotly  # noqa: F401
        logger.info("plotly is available — chart generation enabled")
    except ImportError:
        logger.warning("plotly is not installed — chart endpoints will return placeholder HTML")

    logger.info(
        "Backtesting service started",
        jobs_db=jobs_db,
        presets_db=presets_db,
    )

    yield

    # Cleanup
    await job_store.close()
    await preset_store.close()
    logger.info("Backtesting service stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Grid Backtesting Service",
        description="Standalone grid backtesting and optimization service",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Import and include routes
    from grid_backtester.api.routes import router
    app.include_router(router)

    return app
