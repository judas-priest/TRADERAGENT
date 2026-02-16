"""
Dashboard API endpoint.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends

from web.backend.auth.models import User
from web.backend.dependencies import get_current_user, get_orchestrators
from web.backend.services.bot_service import BotService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_overview(
    _: User = Depends(get_current_user),
    orchestrators: dict = Depends(get_orchestrators),
):
    """Get aggregated dashboard overview."""
    service = BotService(orchestrators)
    bots = service.list_bots()

    total_profit = sum(b.total_profit for b in bots)
    active_bots = sum(1 for b in bots if b.status == "running")
    total_trades = sum(b.total_trades for b in bots)

    return {
        "active_bots": active_bots,
        "total_bots": len(bots),
        "total_profit": total_profit,
        "total_trades": total_trades,
        "bots": [b.model_dump() for b in bots],
    }
