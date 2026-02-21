"""
Bots API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from web.backend.auth.models import User
from web.backend.dependencies import get_current_user, get_orchestrators
from web.backend.schemas.bot import (
    BotCreateRequest,
    BotCreateResponse,
    BotListResponse,
    BotStatusResponse,
    PnLResponse,
    PositionResponse,
)
from web.backend.schemas.common import SuccessResponse
from web.backend.services.bot_service import BotService

router = APIRouter(prefix="/api/v1/bots", tags=["bots"])


def _get_bot_service(orchestrators: dict = Depends(get_orchestrators)) -> BotService:
    return BotService(orchestrators)


@router.post("", response_model=BotCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(
    data: BotCreateRequest,
    request: Request,
    _: User = Depends(get_current_user),
    orchestrators: dict = Depends(get_orchestrators),
):
    """Create a new bot."""
    if data.name in orchestrators:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bot '{data.name}' already exists",
        )

    from bot.config.schemas import BotConfig
    from bot.config.schemas import ExchangeConfig as BotExchangeConfig

    try:
        bot_config = BotConfig(
            name=data.name,
            symbol=data.symbol,
            strategy=data.strategy,
            exchange=BotExchangeConfig(
                exchange_id=data.exchange_id,
                credentials_name=data.credentials_name,
                sandbox=data.dry_run,
            ),
            grid=data.grid,
            dca=data.dca,
            trend_follower=data.trend_follower,
            smc=data.smc,
            risk_management=data.risk_management,
            dry_run=data.dry_run,
            auto_start=False,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    from bot.orchestrator.bot_orchestrator import BotOrchestrator

    db_manager = request.app.state.db_manager
    orch = BotOrchestrator(
        bot_config=bot_config,
        exchange_client=None,
        db_manager=db_manager,
    )
    orchestrators[data.name] = orch

    return BotCreateResponse(
        name=data.name,
        symbol=data.symbol,
        strategy=str(data.strategy),
        dry_run=data.dry_run,
        message=f"Bot '{data.name}' created successfully",
    )


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
