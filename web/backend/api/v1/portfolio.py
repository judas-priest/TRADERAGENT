"""
Portfolio API endpoints.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends

from web.backend.auth.models import User
from web.backend.dependencies import get_current_user, get_orchestrators
from web.backend.schemas.portfolio import DrawdownMetrics, PortfolioSummary
from web.backend.services.bot_service import BotService

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
async def get_summary(
    _: User = Depends(get_current_user),
    orchestrators: dict = Depends(get_orchestrators),
):
    """Get portfolio summary across all bots."""
    service = BotService(orchestrators)
    bots = service.list_bots()

    total_realized = Decimal("0")
    total_unrealized = Decimal("0")
    allocation = []

    for bot_info in bots:
        pnl = await service.get_pnl(bot_info.name)
        if pnl:
            total_realized += pnl.total_realized_pnl
            total_unrealized += pnl.total_unrealized_pnl

        allocation.append(
            {
                "bot": bot_info.name,
                "strategy": bot_info.strategy,
                "symbol": bot_info.symbol,
                "profit": float(bot_info.total_profit),
            }
        )

    return PortfolioSummary(
        total_balance=total_realized + total_unrealized,
        total_realized_pnl=total_realized,
        total_unrealized_pnl=total_unrealized,
        active_bots=sum(1 for b in bots if b.status == "running"),
        total_bots=len(bots),
        allocation=allocation,
    )


@router.get("/history")
async def get_history(
    _: User = Depends(get_current_user),
):
    """Get balance history (equity curve)."""
    # TODO: Query performance_snapshots table when populated
    return {"history": [], "message": "Balance history requires performance snapshots collection"}


@router.get("/allocation")
async def get_allocation(
    _: User = Depends(get_current_user),
    orchestrators: dict = Depends(get_orchestrators),
):
    """Get asset allocation by bot/strategy."""
    service = BotService(orchestrators)
    bots = service.list_bots()

    by_strategy = {}
    for bot in bots:
        key = bot.strategy
        if key not in by_strategy:
            by_strategy[key] = {"strategy": key, "bots": 0, "total_profit": Decimal("0")}
        by_strategy[key]["bots"] += 1
        by_strategy[key]["total_profit"] += bot.total_profit

    return {
        "by_strategy": [
            {**v, "total_profit": float(v["total_profit"])} for v in by_strategy.values()
        ],
        "by_bot": [
            {
                "name": b.name,
                "strategy": b.strategy,
                "symbol": b.symbol,
                "profit": float(b.total_profit),
            }
            for b in bots
        ],
    }


@router.get("/drawdown", response_model=DrawdownMetrics)
async def get_drawdown(
    _: User = Depends(get_current_user),
):
    """Get drawdown metrics."""
    # TODO: Calculate from performance_snapshots
    return DrawdownMetrics()


@router.get("/trades")
async def get_all_trades(
    page: int = 1,
    per_page: int = 20,
    _: User = Depends(get_current_user),
):
    """Get all trades across all bots."""
    # TODO: Query trades table with pagination
    return {"items": [], "total": 0, "page": page, "per_page": per_page, "pages": 0}
