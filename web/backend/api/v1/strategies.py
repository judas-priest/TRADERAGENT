"""
Strategies API endpoints — marketplace and copy-trading.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.schemas import (
    DCAConfig,
    GridConfig,
    SMCConfigSchema,
    TrendFollowerConfig,
)
from bot.database.models import StrategyTemplate
from web.backend.auth.models import User
from web.backend.dependencies import get_current_admin, get_current_user, get_db
from web.backend.schemas.strategy import (
    CopyStrategyRequest,
    StrategyTemplateCreate,
    StrategyTemplateResponse,
    StrategyTypeInfo,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


def _template_to_response(t: StrategyTemplate) -> StrategyTemplateResponse:
    """Convert DB model to response schema."""
    pairs = []
    if t.recommended_pairs:
        try:
            pairs = json.loads(t.recommended_pairs)
        except (json.JSONDecodeError, TypeError):
            pairs = []

    return StrategyTemplateResponse(
        id=t.id,
        name=t.name,
        description=t.description,
        strategy_type=t.strategy_type,
        config_json=t.config_json,
        risk_level=t.risk_level,
        min_deposit=t.min_deposit,
        expected_pnl_pct=t.expected_pnl_pct,
        recommended_pairs=pairs,
        is_active=t.is_active,
        copy_count=t.copy_count,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("/templates", response_model=list[StrategyTemplateResponse])
async def list_templates(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List strategy templates (marketplace)."""
    result = await db.execute(
        select(StrategyTemplate).where(StrategyTemplate.is_active == True)  # noqa: E712
    )
    templates = result.scalars().all()
    return [_template_to_response(t) for t in templates]


@router.post(
    "/templates",
    response_model=StrategyTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: StrategyTemplateCreate,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a strategy template (admin only)."""
    template = StrategyTemplate(
        name=data.name,
        description=data.description,
        strategy_type=data.strategy_type,
        config_json=data.config_json,
        risk_level=data.risk_level,
        min_deposit=data.min_deposit,
        expected_pnl_pct=data.expected_pnl_pct,
        recommended_pairs=json.dumps(data.recommended_pairs),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return _template_to_response(template)


@router.get("/templates/{template_id}", response_model=StrategyTemplateResponse)
async def get_template(
    template_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get strategy template details."""
    result = await db.execute(
        select(StrategyTemplate).where(StrategyTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_to_response(template)


@router.post("/copy")
async def copy_strategy(
    data: CopyStrategyRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Copy a strategy template to create a new bot."""
    result = await db.execute(
        select(StrategyTemplate).where(StrategyTemplate.id == data.template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Increment copy count
    template.copy_count = (template.copy_count or 0) + 1
    await db.commit()

    return {
        "message": f"Strategy '{template.name}' copied as bot '{data.bot_name}'",
        "bot_name": data.bot_name,
        "symbol": data.symbol,
        "template_id": data.template_id,
    }


@router.get("/types", response_model=list[StrategyTypeInfo])
async def list_strategy_types(
    _: User = Depends(get_current_user),
):
    """List available strategy types with parameter schemas."""
    types = [
        StrategyTypeInfo(
            name="grid",
            description="Grid Trading — places buy/sell orders at fixed intervals",
            config_schema=GridConfig.model_json_schema(),
        ),
        StrategyTypeInfo(
            name="dca",
            description="DCA — Dollar Cost Averaging with safety orders",
            config_schema=DCAConfig.model_json_schema(),
        ),
        StrategyTypeInfo(
            name="trend_follower",
            description="Trend Follower — EMA/RSI based trend following",
            config_schema=TrendFollowerConfig.model_json_schema(),
        ),
        StrategyTypeInfo(
            name="smc",
            description="Smart Money Concepts — institutional order flow analysis",
            config_schema=SMCConfigSchema.model_json_schema(),
            coming_soon=True,
        ),
    ]
    return types
