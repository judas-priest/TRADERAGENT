"""
Market data API endpoints.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from web.backend.auth.models import User
from web.backend.dependencies import get_current_user, get_orchestrators
from web.backend.schemas.market import OHLCVCandle, TickerResponse

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/ticker/{symbol}", response_model=TickerResponse)
async def get_ticker(
    symbol: str,
    _: User = Depends(get_current_user),
    orchestrators: dict = Depends(get_orchestrators),
):
    """Get current ticker for a symbol."""
    # Try to get from any orchestrator's exchange client
    for orch in orchestrators.values():
        try:
            if hasattr(orch, "exchange") and orch.exchange:
                ticker = await orch.exchange.fetch_ticker(symbol)
                return TickerResponse(
                    symbol=symbol,
                    last=Decimal(str(ticker.get("last", 0))),
                    bid=Decimal(str(ticker["bid"])) if ticker.get("bid") else None,
                    ask=Decimal(str(ticker["ask"])) if ticker.get("ask") else None,
                    high=Decimal(str(ticker["high"])) if ticker.get("high") else None,
                    low=Decimal(str(ticker["low"])) if ticker.get("low") else None,
                    volume=Decimal(str(ticker["quoteVolume"])) if ticker.get("quoteVolume") else None,
                    change_pct=ticker.get("percentage"),
                )
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="No exchange client available")


@router.get("/ohlcv/{symbol}", response_model=list[OHLCVCandle])
async def get_ohlcv(
    symbol: str,
    timeframe: str = Query(default="1h", description="Candle timeframe"),
    limit: int = Query(default=100, ge=1, le=1000),
    _: User = Depends(get_current_user),
    orchestrators: dict = Depends(get_orchestrators),
):
    """Get OHLCV candles for a symbol."""
    for orch in orchestrators.values():
        try:
            if hasattr(orch, "exchange") and orch.exchange:
                candles = await orch.exchange.fetch_ohlcv(
                    symbol, timeframe=timeframe, limit=limit
                )
                return [
                    OHLCVCandle(
                        timestamp=int(c[0]),
                        open=Decimal(str(c[1])),
                        high=Decimal(str(c[2])),
                        low=Decimal(str(c[3])),
                        close=Decimal(str(c[4])),
                        volume=Decimal(str(c[5])),
                    )
                    for c in candles
                ]
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="No exchange client available")
