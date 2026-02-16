"""
Backtesting API schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    strategy_type: str
    symbol: str
    timeframe: str = "1h"
    start_date: datetime
    end_date: datetime
    initial_balance: Decimal = Field(default=Decimal("10000"), gt=0)
    config: dict = {}


class BacktestJobResponse(BaseModel):
    job_id: str
    status: str
    strategy_type: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    created_at: datetime
    completed_at: datetime | None = None
    result: dict | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
