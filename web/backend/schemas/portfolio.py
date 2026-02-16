"""
Portfolio API schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PortfolioSummary(BaseModel):
    total_balance: Decimal = Decimal("0")
    total_realized_pnl: Decimal = Decimal("0")
    total_unrealized_pnl: Decimal = Decimal("0")
    active_bots: int = 0
    total_bots: int = 0
    allocation: list[dict] = []


class BalanceHistoryPoint(BaseModel):
    timestamp: datetime
    balance: Decimal


class DrawdownMetrics(BaseModel):
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_amount: Decimal = Decimal("0")
    recovery_time_hours: float | None = None
