"""
Backtesting API endpoints — async job execution with real GridBacktestSimulator.
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

_backtester_src = str(Path(__file__).resolve().parent.parent.parent.parent.parent / "services" / "backtesting" / "src")
if _backtester_src not in sys.path:
    sys.path.insert(0, _backtester_src)

from grid_backtester.engine import GridBacktestConfig, GridBacktestSimulator

from web.backend.auth.models import User
from web.backend.dependencies import get_current_user, get_orchestrators
from web.backend.schemas.backtest import BacktestJobResponse, BacktestRunRequest

router = APIRouter(prefix="/api/v1/backtesting", tags=["backtesting"])

# In-memory job store (production: use backtest_jobs table)
_jobs: dict[str, dict] = {}
_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent backtests


@router.post("/run", response_model=BacktestJobResponse, status_code=202)
async def run_backtest(
    data: BacktestRunRequest,
    _: User = Depends(get_current_user),
    orchestrators: dict = Depends(get_orchestrators),
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

    # Get exchange client for fetching OHLCV data
    exchange = None
    for orch in orchestrators.values():
        if hasattr(orch, "exchange") and orch.exchange:
            exchange = orch.exchange
            break

    # Start backtest in background
    asyncio.create_task(_execute_backtest(job_id, data, exchange))

    return BacktestJobResponse(**job)


@router.get("/history", response_model=list[BacktestJobResponse])
async def get_backtest_history(
    _: User = Depends(get_current_user),
):
    """Get past backtest results."""
    return [BacktestJobResponse(**j) for j in _jobs.values()]


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


@router.get("/data/pairs")
async def get_available_pairs(
    _: User = Depends(get_current_user),
):
    """Get available trading pairs for backtesting."""
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


async def _execute_backtest(job_id: str, data: BacktestRunRequest, exchange=None):
    """Execute backtest in background with semaphore."""
    async with _semaphore:
        job = _jobs[job_id]
        job["status"] = "running"

        try:
            if data.strategy_type == "grid" and exchange:
                result = await _run_grid_backtest(data, exchange)
            elif data.strategy_type == "grid":
                result = await asyncio.to_thread(_run_grid_backtest_offline, data)
            else:
                raise ValueError(
                    f"Backtesting for strategy '{data.strategy_type}' is not yet implemented. "
                    f"Available: grid"
                )

            job["status"] = "completed"
            job["result"] = result
            job["completed_at"] = datetime.now(timezone.utc)
        except Exception as e:
            job["status"] = "failed"
            job["error_message"] = str(e)
            job["completed_at"] = datetime.now(timezone.utc)


async def _run_grid_backtest(data: BacktestRunRequest, exchange) -> dict:
    """Run grid backtest with real OHLCV data from exchange."""
    # Fetch OHLCV data
    ohlcv = await exchange.fetch_ohlcv(
        symbol=data.symbol,
        timeframe=data.timeframe,
        limit=1000,
    )

    if not ohlcv or len(ohlcv) < 50:
        raise ValueError(f"Insufficient OHLCV data for {data.symbol}: got {len(ohlcv or [])} candles")

    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    # Build config from request
    user_config = data.config or {}
    config = GridBacktestConfig(
        symbol=data.symbol,
        timeframe=data.timeframe,
        num_levels=user_config.get("num_levels", 15),
        profit_per_grid=Decimal(str(user_config.get("profit_per_grid", 0.005))),
        amount_per_grid=Decimal(str(user_config.get("amount_per_grid", 100))),
        initial_balance=Decimal(str(data.initial_balance)),
    )

    # Run real simulator
    sim = GridBacktestSimulator(config)
    result = await asyncio.to_thread(sim.run, df)

    return {
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "profit_factor": getattr(result, "profit_factor", 0),
        "total_pnl": result.total_pnl,
        "final_equity": result.final_equity,
        "completed_cycles": result.completed_cycles,
        "total_fees_paid": result.total_fees_paid,
        "equity_curve": [
            {"timestamp": str(ep.timestamp), "equity": ep.equity, "price": ep.price}
            for ep in (result.equity_curve or [])[:200]  # limit to 200 points
        ],
    }


def _run_grid_backtest_offline(data: BacktestRunRequest) -> dict:
    """Run grid backtest without exchange (generates synthetic data)."""
    import numpy as np

    # Generate synthetic OHLCV data
    np.random.seed(42)
    n_candles = 500
    prices = [float(data.config.get("base_price", 50000))]
    for _ in range(n_candles - 1):
        change = np.random.normal(0, 0.005)
        prices.append(prices[-1] * (1 + change))

    df = pd.DataFrame({
        "timestamp": pd.date_range(start=data.start_date, periods=n_candles, freq="1h"),
        "open": prices,
        "high": [p * (1 + abs(np.random.normal(0, 0.002))) for p in prices],
        "low": [p * (1 - abs(np.random.normal(0, 0.002))) for p in prices],
        "close": [p * (1 + np.random.normal(0, 0.001)) for p in prices],
        "volume": [np.random.uniform(100, 1000) for _ in prices],
    })

    user_config = data.config or {}
    config = GridBacktestConfig(
        symbol=data.symbol,
        timeframe=data.timeframe,
        num_levels=user_config.get("num_levels", 15),
        profit_per_grid=Decimal(str(user_config.get("profit_per_grid", 0.005))),
        amount_per_grid=Decimal(str(user_config.get("amount_per_grid", 100))),
        initial_balance=Decimal(str(data.initial_balance)),
    )

    sim = GridBacktestSimulator(config)
    result = sim.run(df)

    return {
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "profit_factor": getattr(result, "profit_factor", 0),
        "total_pnl": result.total_pnl,
        "final_equity": result.final_equity,
        "completed_cycles": result.completed_cycles,
        "total_fees_paid": result.total_fees_paid,
        "equity_curve": [
            {"timestamp": str(ep.timestamp), "equity": ep.equity, "price": ep.price}
            for ep in (result.equity_curve or [])[:200]
        ],
        "_note": "Results based on synthetic data (no exchange connection available)",
    }
