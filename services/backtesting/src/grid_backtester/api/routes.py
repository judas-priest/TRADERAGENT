"""
API routes for the grid backtesting service (Issue #9 + #12).

Endpoints:
- POST /api/v1/backtest/run — submit backtest job (202)
- GET  /api/v1/backtest/{job_id} — get job status/result
- GET  /api/v1/backtest/history — list jobs
- POST /api/v1/optimize/run — submit optimization job (202)
- GET  /api/v1/presets — list presets
- GET  /api/v1/presets/{symbol} — get preset for symbol
- POST /api/v1/presets — create preset
- DELETE /api/v1/presets/{preset_id} — delete preset
- GET  /api/v1/chart/{job_id} — get chart HTML
- GET  /health — health check
"""

import asyncio
from decimal import Decimal
from functools import partial
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from grid_backtester.api.auth import verify_api_key
from grid_backtester.engine.models import GridBacktestConfig, GridBacktestResult, GridDirection, OptimizationObjective
from grid_backtester.engine.simulator import GridBacktestSimulator
from grid_backtester.engine.system import GridBacktestSystem
from grid_backtester.visualization.charts import GridChartGenerator
from grid_backtester.core.calculator import GridSpacing
from grid_backtester.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class BacktestRequest(BaseModel):
    symbol: str = "BTCUSDT"
    timeframe: str = "1h"
    num_levels: int = Field(default=15, ge=2, le=100)
    spacing: str = Field(default="arithmetic", pattern="^(arithmetic|geometric)$")
    profit_per_grid: float = Field(default=0.005, ge=0, le=1)
    amount_per_grid: float = Field(default=100, gt=0)
    initial_balance: float = Field(default=10000, gt=0)
    stop_loss_pct: float = Field(default=0.05, ge=0, le=1)
    max_drawdown_pct: float = Field(default=0.10, ge=0, le=1)
    take_profit_pct: float = Field(default=0, ge=0, le=10)
    direction: str = Field(default="neutral")
    candles: list[dict[str, Any]] | None = None
    candles_csv_path: str | None = None


class OptimizeRequest(BaseModel):
    symbol: str = "BTCUSDT"
    objective: str = Field(default="sharpe")
    coarse_steps: int = Field(default=3, ge=2, le=10)
    fine_steps: int = Field(default=3, ge=2, le=10)
    initial_balance: float = Field(default=10000, gt=0)
    max_workers: int | None = Field(default=None, ge=1, le=16)
    candles: list[dict[str, Any]] | None = None
    candles_csv_path: str | None = None


class PresetCreate(BaseModel):
    symbol: str
    config_yaml: str
    cluster: str = ""
    metrics: dict[str, Any] | None = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str = ""


# =============================================================================
# Health
# =============================================================================


@router.get("/health")
async def health_check(request: Request) -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "grid-backtester",
        "version": "1.0.0",
    }


# =============================================================================
# Backtest
# =============================================================================


@router.post(
    "/api/v1/backtest/run",
    response_model=JobResponse,
    status_code=202,
)
async def run_backtest(
    req: BacktestRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
) -> JobResponse:
    """Submit a backtest job."""
    job_store = request.app.state.job_store

    config_dict = req.model_dump()
    job_id = await job_store.create(job_type="backtest", config=config_dict)

    background_tasks.add_task(_execute_backtest, request.app, job_id, req)

    return JobResponse(job_id=job_id, status="pending", message="Backtest job submitted")


async def _execute_backtest(app: Any, job_id: str, req: BacktestRequest) -> None:
    """Execute backtest in background."""
    job_store = app.state.job_store
    preset_store = app.state.preset_store

    try:
        await job_store.update_status(job_id, "running")

        candles = _load_candles(req.candles, req.candles_csv_path)
        if candles is None or len(candles) < 2:
            await job_store.update_status(job_id, "failed", error="No candle data provided or insufficient candles")
            return

        config = GridBacktestConfig(
            symbol=req.symbol,
            timeframe=req.timeframe,
            num_levels=req.num_levels,
            spacing=GridSpacing(req.spacing),
            profit_per_grid=Decimal(str(req.profit_per_grid)),
            amount_per_grid=Decimal(str(req.amount_per_grid)),
            initial_balance=Decimal(str(req.initial_balance)),
            stop_loss_pct=Decimal(str(req.stop_loss_pct)),
            max_drawdown_pct=Decimal(str(req.max_drawdown_pct)),
            take_profit_pct=Decimal(str(req.take_profit_pct)),
            direction=GridDirection(req.direction),
        )

        sim = GridBacktestSimulator(config)
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, sim.run, candles)

        await job_store.update_status(job_id, "completed", result=result.to_dict())

    except Exception as e:
        logger.error("Backtest job failed", job_id=job_id, error=str(e))
        await job_store.update_status(job_id, "failed", error=str(e))


@router.get("/api/v1/backtest/history")
async def list_backtest_jobs(
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List backtest jobs."""
    job_store = request.app.state.job_store
    return await job_store.list_jobs(status=status, limit=limit)


@router.get("/api/v1/backtest/{job_id}")
async def get_backtest_job(
    job_id: str,
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
) -> dict[str, Any]:
    """Get backtest job status and result."""
    job_store = request.app.state.job_store
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# =============================================================================
# Optimize
# =============================================================================


@router.post(
    "/api/v1/optimize/run",
    response_model=JobResponse,
    status_code=202,
)
async def run_optimize(
    req: OptimizeRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
) -> JobResponse:
    """Submit an optimization job."""
    job_store = request.app.state.job_store

    config_dict = req.model_dump()
    job_id = await job_store.create(job_type="optimize", config=config_dict)

    background_tasks.add_task(_execute_optimize, request.app, job_id, req)

    return JobResponse(job_id=job_id, status="pending", message="Optimization job submitted")


async def _execute_optimize(app: Any, job_id: str, req: OptimizeRequest) -> None:
    """Execute optimization in background."""
    job_store = app.state.job_store
    preset_store = app.state.preset_store

    try:
        await job_store.update_status(job_id, "running")

        candles = _load_candles(req.candles, req.candles_csv_path)
        if candles is None or len(candles) < 15:
            await job_store.update_status(job_id, "failed", error="Insufficient candle data")
            return

        # Get cache and checkpoint from app state if available
        indicator_cache = getattr(app.state, "indicator_cache", None)
        checkpoint = getattr(app.state, "checkpoint", None)
        system = GridBacktestSystem(
            max_workers=req.max_workers,
            indicator_cache=indicator_cache,
            checkpoint=checkpoint,
        )

        base_config = GridBacktestConfig(
            symbol=req.symbol,
            initial_balance=Decimal(str(req.initial_balance)),
            stop_loss_pct=Decimal("0.50"),
            max_drawdown_pct=Decimal("0.50"),
        )

        loop = asyncio.get_event_loop()
        pipeline_result = await loop.run_in_executor(
            None,
            partial(
                system.run_full_pipeline,
                symbols=[req.symbol],
                candles_map={req.symbol: candles},
                base_config=base_config,
                objective=OptimizationObjective(req.objective),
                coarse_steps=req.coarse_steps,
                fine_steps=req.fine_steps,
            ),
        )

        await job_store.update_status(job_id, "completed", result=pipeline_result)

        # Auto-save preset if optimization found a result
        per_symbol = pipeline_result.get("per_symbol", {})
        symbol_data = per_symbol.get(req.symbol, {})
        preset_yaml = symbol_data.get("preset_yaml", "")
        if preset_yaml:
            opt_data = symbol_data.get("optimization", {})
            best_result = opt_data.get("best_result", {})
            await preset_store.create(
                symbol=req.symbol,
                config_yaml=preset_yaml,
                cluster=symbol_data.get("profile", {}).get("cluster", ""),
                metrics=best_result,
            )

    except Exception as e:
        logger.error("Optimize job failed", job_id=job_id, error=str(e))
        await job_store.update_status(job_id, "failed", error=str(e))


# =============================================================================
# Presets (Issue #12)
# =============================================================================


@router.get("/api/v1/presets")
async def list_presets(
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
) -> list[dict[str, Any]]:
    """List all active presets."""
    preset_store = request.app.state.preset_store
    return await preset_store.list_presets()


@router.get("/api/v1/presets/{symbol}")
async def get_preset(
    symbol: str,
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
) -> dict[str, Any]:
    """Get active preset for a symbol."""
    preset_store = request.app.state.preset_store
    preset = await preset_store.get_by_symbol(symbol)
    if not preset:
        raise HTTPException(status_code=404, detail=f"No preset found for {symbol}")
    return preset


@router.post("/api/v1/presets", status_code=201)
async def create_preset(
    req: PresetCreate,
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
) -> dict[str, str]:
    """Create a new preset."""
    preset_store = request.app.state.preset_store
    preset_id = await preset_store.create(
        symbol=req.symbol,
        config_yaml=req.config_yaml,
        cluster=req.cluster,
        metrics=req.metrics,
    )
    return {"preset_id": preset_id, "symbol": req.symbol}


@router.delete("/api/v1/presets/{preset_id}")
async def delete_preset(
    preset_id: str,
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
) -> dict[str, str]:
    """Delete a preset."""
    preset_store = request.app.state.preset_store
    deleted = await preset_store.delete(preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"status": "deleted", "preset_id": preset_id}


# =============================================================================
# Charts (Issue #8)
# =============================================================================


@router.get("/api/v1/chart/{job_id}", response_class=HTMLResponse)
async def get_chart(
    job_id: str,
    request: Request,
    api_key: Annotated[str, Depends(verify_api_key)],
) -> HTMLResponse:
    """Get chart HTML for a completed backtest job."""
    job_store = request.app.state.job_store
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")

    result_dict = job.get("result", {})

    # For backtest jobs, reconstruct result and generate chart
    if job.get("job_type") == "backtest":
        result = GridBacktestResult.from_dict(result_dict)
    else:
        # For optimize jobs, extract best result from pipeline output
        per_symbol = result_dict.get("per_symbol", {})
        if per_symbol:
            first_symbol_data = next(iter(per_symbol.values()), {})
            best_result = first_symbol_data.get("optimization", {}).get("best_result", {})
            result = GridBacktestResult.from_dict(best_result) if best_result else GridBacktestResult()
        else:
            result = GridBacktestResult()

    chart_gen = GridChartGenerator()
    html = chart_gen.full_report_html(result)
    return HTMLResponse(content=html)


# =============================================================================
# Helpers
# =============================================================================


def _load_candles(
    candles_data: list[dict[str, Any]] | None,
    csv_path: str | None,
) -> pd.DataFrame | None:
    """Load candles from request data or CSV file."""
    if candles_data:
        return pd.DataFrame(candles_data)
    if csv_path:
        try:
            return pd.read_csv(csv_path)
        except Exception as e:
            logger.error("Failed to load CSV", path=csv_path, error=str(e))
            return None
    return None
