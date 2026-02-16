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
    StrategyType,
    TrendFollowerConfig,
)
from web.backend.auth.models import User
from web.backend.dependencies import get_current_admin, get_current_user, get_db
from web.backend.schemas.strategy import (
    CopyStrategyRequest,
    StrategyTemplateCreate,
    StrategyTemplateResponse,
    StrategyTypeInfo,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


# Use a simple in-memory store until DB model is migrated
# In production, this would be the strategy_templates table
_templates: dict[int, dict] = {}
_next_id = 1


@router.get("/templates", response_model=list[StrategyTemplateResponse])
async def list_templates(
    _: User = Depends(get_current_user),
):
    """List strategy templates (marketplace)."""
    return [
        StrategyTemplateResponse(**t)
        for t in _templates.values()
        if t.get("is_active", True)
    ]


@router.post(
    "/templates",
    response_model=StrategyTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: StrategyTemplateCreate,
    _: User = Depends(get_current_admin),
):
    """Create a strategy template (admin only)."""
    global _next_id
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    template = {
        "id": _next_id,
        "name": data.name,
        "description": data.description,
        "strategy_type": data.strategy_type,
        "config_json": data.config_json,
        "risk_level": data.risk_level,
        "min_deposit": data.min_deposit,
        "expected_pnl_pct": data.expected_pnl_pct,
        "recommended_pairs": data.recommended_pairs,
        "is_active": True,
        "copy_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    _templates[_next_id] = template
    _next_id += 1
    return StrategyTemplateResponse(**template)


@router.get("/templates/{template_id}", response_model=StrategyTemplateResponse)
async def get_template(
    template_id: int,
    _: User = Depends(get_current_user),
):
    """Get strategy template details."""
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return StrategyTemplateResponse(**template)


@router.post("/copy")
async def copy_strategy(
    data: CopyStrategyRequest,
    _: User = Depends(get_current_user),
):
    """Copy a strategy template to create a new bot."""
    template = _templates.get(data.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Increment copy count
    template["copy_count"] = template.get("copy_count", 0) + 1

    return {
        "message": f"Strategy '{template['name']}' copied as bot '{data.bot_name}'",
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
    ]
    return types
