"""
Market data API schemas.
"""

from decimal import Decimal

from pydantic import BaseModel


class TickerResponse(BaseModel):
    symbol: str
    last: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: Decimal | None = None
    change_pct: float | None = None


class OHLCVCandle(BaseModel):
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
