"""
Bots API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from web.backend.auth.models import User
from web.backend.dependencies import get_current_user, get_orchestrators
from web.backend.schemas.bot import (
    BotCreateRequest,
    BotListResponse,
    BotStatusResponse,
    BotUpdateRequest,
    PnLResponse,
    PositionResponse,
    TradeResponse,
)
from web.backend.schemas.common import SuccessResponse
from web.backend.services.bot_service import BotService

router = APIRouter(prefix="/api/v1/bots", tags=["bots"])


def _get_bot_service(orchestrators: dict = Depends(get_orchestrators)) -> BotService:
    return BotService(orchestrators)


@router.get("", response_model=list[BotListResponse])
async def list_bots(
    strategy: str | None = Query(None, description="Filter by strategy type"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """List all bots with optional filters."""
    return await service.list_bots(strategy=strategy, status_filter=status_filter, symbol=symbol)


@router.get("/{bot_name}", response_model=BotStatusResponse)
async def get_bot(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Get detailed bot status."""
    result = await service.get_bot_status(bot_name)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    return result


@router.post("/{bot_name}/start", response_model=SuccessResponse)
async def start_bot(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Start a bot."""
    success = await service.start_bot(bot_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    return SuccessResponse(message=f"Bot '{bot_name}' started")


@router.post("/{bot_name}/stop", response_model=SuccessResponse)
async def stop_bot(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Stop a bot."""
    success = await service.stop_bot(bot_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    return SuccessResponse(message=f"Bot '{bot_name}' stopped")


@router.post("/{bot_name}/pause", response_model=SuccessResponse)
async def pause_bot(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Pause a bot."""
    success = await service.pause_bot(bot_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    return SuccessResponse(message=f"Bot '{bot_name}' paused")


@router.post("/{bot_name}/resume", response_model=SuccessResponse)
async def resume_bot(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Resume a bot."""
    success = await service.resume_bot(bot_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    return SuccessResponse(message=f"Bot '{bot_name}' resumed")


@router.post("/{bot_name}/emergency-stop", response_model=SuccessResponse)
async def emergency_stop_bot(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Emergency stop a bot."""
    success = await service.emergency_stop(bot_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    return SuccessResponse(message=f"Bot '{bot_name}' emergency stopped")


@router.get("/{bot_name}/positions", response_model=list[PositionResponse])
async def get_positions(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Get active positions for a bot."""
    return await service.get_positions(bot_name)


@router.get("/{bot_name}/pnl", response_model=PnLResponse)
async def get_pnl(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Get PnL metrics for a bot."""
    result = await service.get_pnl(bot_name)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    return result


@router.post("", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(
    data: BotCreateRequest,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Create a new bot configuration."""
    success, message = await service.create_bot(data)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return SuccessResponse(message=message)


@router.put("/{bot_name}", response_model=SuccessResponse)
async def update_bot(
    bot_name: str,
    data: BotUpdateRequest,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Update bot configuration."""
    success, message = await service.update_bot(bot_name, data)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    return SuccessResponse(message=message)


@router.delete("/{bot_name}", response_model=SuccessResponse)
async def delete_bot(
    bot_name: str,
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Delete a bot (must be stopped first)."""
    success, message = await service.delete_bot(bot_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return SuccessResponse(message=message)


@router.get("/{bot_name}/trades", response_model=list[TradeResponse])
async def get_trades(
    bot_name: str,
    limit: int = Query(50, ge=1, le=500, description="Number of trades to return"),
    _: User = Depends(get_current_user),
    service: BotService = Depends(_get_bot_service),
):
    """Get trade history for a bot."""
    return await service.get_trades(bot_name, limit=limit)
