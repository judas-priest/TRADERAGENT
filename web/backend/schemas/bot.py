"""
Bot API schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from bot.config.schemas import (
    DCAConfig,
    GridConfig,
    RiskManagementConfig,
    SMCConfigSchema,
    StrategyType,
    TrendFollowerConfig,
)


class BotCreateRequest(BaseModel):
    """Request to create a new bot."""

    name: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., description="Trading pair (e.g., BTC/USDT)")
    strategy: StrategyType
    exchange_id: str = Field(default="binance", description="Exchange identifier")
    credentials_name: str = Field(default="default", description="Name of stored credentials")
    grid: GridConfig | None = None
    dca: DCAConfig | None = None
    trend_follower: TrendFollowerConfig | None = None
    smc: SMCConfigSchema | None = None
    risk_management: RiskManagementConfig = Field(
        default_factory=lambda: RiskManagementConfig(max_position_size=Decimal("1000"))
    )
    dry_run: bool = True
    auto_start: bool = False


class BotCreateResponse(BaseModel):
    """Response after bot creation."""

    name: str
    symbol: str
    strategy: str
    dry_run: bool
    message: str


class BotUpdateRequest(BaseModel):
    """Request to update bot config (risk params only for non-admins)."""

    dry_run: bool | None = None
    risk_management: RiskManagementConfig | None = None
    grid: GridConfig | None = None
    dca: DCAConfig | None = None
    trend_follower: TrendFollowerConfig | None = None


class BotStatusResponse(BaseModel):
    """Bot status from orchestrator."""

    name: str
    strategy: str
    symbol: str
    status: str
    dry_run: bool = False
    uptime_seconds: float | None = None
    total_trades: int = 0
    total_profit: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    active_positions: int = 0
    open_orders: int = 0
    last_trade_at: datetime | None = None
    config: dict | None = None


class BotListResponse(BaseModel):
    """Bot list item."""

    name: str
    strategy: str
    symbol: str
    status: str
    total_trades: int = 0
    total_profit: Decimal = Decimal("0")
    active_positions: int = 0


class TradeResponse(BaseModel):
    """Trade record."""

    id: int
    symbol: str
    side: str
    price: Decimal
    amount: Decimal
    fee: Decimal = Decimal("0")
    profit: Decimal | None = None
    executed_at: datetime

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    """Active position."""

    symbol: str
    side: str
    size: Decimal
    entry_price: Decimal
    current_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    leverage: int = 1


class PnLResponse(BaseModel):
    """PnL metrics."""

    total_realized_pnl: Decimal = Decimal("0")
    total_unrealized_pnl: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    win_rate: float | None = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
