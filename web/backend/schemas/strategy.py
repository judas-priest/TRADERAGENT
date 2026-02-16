"""
Strategy API schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StrategyTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    strategy_type: str
    config_json: str
    risk_level: str = Field(default="medium", pattern="^(low|medium|high)$")
    min_deposit: Decimal = Decimal("100")
    expected_pnl_pct: Decimal | None = None
    recommended_pairs: list[str] = []


class StrategyTemplateResponse(BaseModel):
    id: int
    name: str
    description: str
    strategy_type: str
    config_json: str
    risk_level: str
    min_deposit: Decimal
    expected_pnl_pct: Decimal | None = None
    recommended_pairs: list[str] = []
    is_active: bool = True
    copy_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CopyStrategyRequest(BaseModel):
    template_id: int
    bot_name: str = Field(..., min_length=1, max_length=100)
    symbol: str
    deposit_amount: Decimal = Field(..., gt=0)
    risk_overrides: dict | None = None


class StrategyTypeInfo(BaseModel):
    name: str
    description: str
    config_schema: dict
