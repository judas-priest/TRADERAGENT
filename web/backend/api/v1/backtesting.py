"""
Backtesting API endpoints — async job execution.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from web.backend.auth.models import User
from web.backend.dependencies import get_current_user
from web.backend.schemas.backtest import BacktestJobResponse, BacktestRunRequest

router = APIRouter(prefix="/api/v1/backtesting", tags=["backtesting"])

# In-memory job store (production: use backtest_jobs table)
_jobs: dict[str, dict] = {}
_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent backtests


@router.post("/run", response_model=BacktestJobResponse, status_code=202)
async def run_backtest(
    data: BacktestRunRequest,
    _: User = Depends(get_current_user),
):
    """Start a backtest (async). Returns job_id to poll for results."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    job = {
        "job_id": job_id,
        "status": "pending",
        "strategy_type": data.strategy_type,
        "symbol": data.symbol,
        "timeframe": data.timeframe,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "created_at": now,
        "completed_at": None,
        "result": None,
        "error_message": None,
    }
    _jobs[job_id] = job

    # Start backtest in background
    asyncio.create_task(_execute_backtest(job_id, data))

    return BacktestJobResponse(**job)


@router.get("/{job_id}", response_model=BacktestJobResponse)
async def get_backtest_result(
    job_id: str,
    _: User = Depends(get_current_user),
):
    """Get backtest job status/result."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Backtest job not found")
    return BacktestJobResponse(**job)


@router.get("/history", response_model=list[BacktestJobResponse])
async def get_backtest_history(
    _: User = Depends(get_current_user),
):
    """Get past backtest results."""
    return [BacktestJobResponse(**j) for j in _jobs.values()]


@router.get("/data/pairs")
async def get_available_pairs(
    _: User = Depends(get_current_user),
):
    """Get available trading pairs for backtesting."""
    # From historical data in /home/hive/btc/data/historical/
    pairs = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
        "DOGEUSDT", "XRPUSDT", "DOTUSDT", "LINKUSDT", "AVAXUSDT",
        "LTCUSDT", "UNIUSDT", "MATICUSDT", "AAVEUSDT", "FTMUSDT",
    ]
    return {"pairs": pairs}


@router.get("/data/timeframes")
async def get_available_timeframes(
    _: User = Depends(get_current_user),
):
    """Get available timeframes for backtesting."""
    return {
        "timeframes": ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]
    }


async def _execute_backtest(job_id: str, data: BacktestRunRequest):
    """Execute backtest in background with semaphore."""
    async with _semaphore:
        job = _jobs[job_id]
        job["status"] = "running"

        try:
            # Run backtest in thread to avoid blocking
            result = await asyncio.to_thread(_run_backtest_sync, data)
            job["status"] = "completed"
            job["result"] = result
            job["completed_at"] = datetime.now(timezone.utc)
        except Exception as e:
            job["status"] = "failed"
            job["error_message"] = str(e)
            job["completed_at"] = datetime.now(timezone.utc)


def _run_backtest_sync(data: BacktestRunRequest) -> dict:
    """Synchronous backtest execution (placeholder)."""
    # TODO: Integrate with BacktestingEngine from bot/backtesting/
    import time

    time.sleep(0.1)  # Simulate work

    return {
        "total_return_pct": 15.5,
        "max_drawdown_pct": 8.2,
        "sharpe_ratio": 1.45,
        "win_rate": 0.62,
        "total_trades": 150,
        "profit_factor": 1.8,
        "equity_curve": [],
    }
