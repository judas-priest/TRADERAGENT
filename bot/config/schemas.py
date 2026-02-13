"""
Pydantic schemas for configuration validation.
Defines the structure and validation rules for bot configurations.
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class StrategyType(str, Enum):
    """Trading strategy types"""

    GRID = "grid"
    DCA = "dca"
    HYBRID = "hybrid"


class ExchangeConfig(BaseModel):
    """Exchange connection configuration"""

    exchange_id: str = Field(
        ...,
        description="Exchange identifier (e.g., 'binance', 'bybit')",
        examples=["binance", "bybit", "okx"],
    )
    credentials_name: str = Field(..., description="Name of stored credentials to use")
    sandbox: bool = Field(default=False, description="Use testnet/sandbox mode")
    rate_limit: bool = Field(default=True, description="Enable rate limiting")


class GridConfig(BaseModel):
    """Grid trading strategy configuration"""

    enabled: bool = Field(default=True, description="Enable grid trading")
    upper_price: Decimal = Field(
        ...,
        gt=0,
        description="Upper price boundary for grid",
    )
    lower_price: Decimal = Field(
        ...,
        gt=0,
        description="Lower price boundary for grid",
    )
    grid_levels: int = Field(
        ...,
        ge=2,
        le=100,
        description="Number of grid levels",
    )
    amount_per_grid: Decimal = Field(
        ...,
        gt=0,
        description="Amount to trade per grid level",
    )
    profit_per_grid: Decimal = Field(
        default=Decimal("0.01"),
        gt=0,
        le=1,
        description="Profit percentage per grid (0.01 = 1%)",
    )

    @model_validator(mode="after")
    def validate_price_range(self) -> "GridConfig":
        """Ensure upper price is greater than lower price"""
        if self.upper_price <= self.lower_price:
            raise ValueError("upper_price must be greater than lower_price")
        return self


class DCAConfig(BaseModel):
    """DCA (Dollar Cost Averaging) configuration"""

    enabled: bool = Field(default=True, description="Enable DCA")
    trigger_percentage: Decimal = Field(
        default=Decimal("0.05"),
        gt=0,
        le=1,
        description="Price drop percentage to trigger DCA (0.05 = 5%)",
    )
    amount_per_step: Decimal = Field(
        ...,
        gt=0,
        description="Amount to buy per DCA step",
    )
    max_steps: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of DCA steps",
    )
    take_profit_percentage: Decimal = Field(
        default=Decimal("0.1"),
        gt=0,
        description="Take profit percentage after DCA (0.1 = 10%)",
    )


class RiskManagementConfig(BaseModel):
    """Risk management configuration"""

    max_position_size: Decimal = Field(
        ...,
        gt=0,
        description="Maximum position size in quote currency",
    )
    stop_loss_percentage: Decimal | None = Field(
        default=None,
        gt=0,
        le=1,
        description="Stop loss percentage (0.2 = 20%)",
    )
    max_daily_loss: Decimal | None = Field(
        default=None,
        gt=0,
        description="Maximum daily loss in quote currency",
    )
    min_order_size: Decimal = Field(
        default=Decimal("10"),
        gt=0,
        description="Minimum order size in quote currency",
    )


class NotificationConfig(BaseModel):
    """Notification configuration"""

    enabled: bool = Field(default=False, description="Enable notifications")
    telegram_bot_token: str | None = Field(default=None, description="Telegram bot token")
    telegram_chat_id: str | None = Field(default=None, description="Telegram chat ID")
    notify_on_trade: bool = Field(default=True, description="Notify on trade execution")
    notify_on_error: bool = Field(default=True, description="Notify on errors")


class BotConfig(BaseModel):
    """Main bot configuration"""

    version: int = Field(default=1, ge=1, description="Configuration version")
    name: str = Field(..., min_length=1, max_length=100, description="Bot name")
    symbol: str = Field(..., description="Trading pair symbol (e.g., 'BTC/USDT')")
    strategy: StrategyType = Field(..., description="Trading strategy type")

    # Sub-configurations
    exchange: ExchangeConfig
    grid: GridConfig | None = Field(default=None, description="Grid trading configuration")
    dca: DCAConfig | None = Field(default=None, description="DCA configuration")
    risk_management: RiskManagementConfig
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)

    # Operational settings
    dry_run: bool = Field(default=False, description="Run in simulation mode without real orders")
    auto_start: bool = Field(default=False, description="Auto-start bot on initialization")

    @model_validator(mode="after")
    def validate_strategy_config(self) -> "BotConfig":
        """Ensure strategy has corresponding configuration"""
        if self.strategy in (StrategyType.GRID, StrategyType.HYBRID):
            if self.grid is None:
                raise ValueError(f"Strategy '{self.strategy}' requires grid configuration")
        if self.strategy in (StrategyType.DCA, StrategyType.HYBRID):
            if self.dca is None:
                raise ValueError(f"Strategy '{self.strategy}' requires dca configuration")
        return self

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "version": 1,
                "name": "BTC_Grid_Bot_1",
                "symbol": "BTC/USDT",
                "strategy": "grid",
                "exchange": {
                    "exchange_id": "binance",
                    "credentials_name": "binance_main",
                    "sandbox": False,
                },
                "grid": {
                    "enabled": True,
                    "upper_price": 50000,
                    "lower_price": 40000,
                    "grid_levels": 10,
                    "amount_per_grid": 100,
                    "profit_per_grid": 0.01,
                },
                "risk_management": {
                    "max_position_size": 10000,
                    "stop_loss_percentage": 0.15,
                    "min_order_size": 10,
                },
                "dry_run": False,
                "auto_start": False,
            }
        }


class AppConfig(BaseModel):
    """Application-wide configuration"""

    # Database
    database_url: str = Field(..., description="PostgreSQL database URL")
    database_pool_size: int = Field(
        default=5, ge=1, le=50, description="Database connection pool size"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )
    log_to_file: bool = Field(default=True, description="Enable file logging")
    log_to_console: bool = Field(default=True, description="Enable console logging")
    json_logs: bool = Field(default=False, description="Use JSON format for logs")

    # Encryption
    encryption_key: str = Field(
        ..., description="Encryption key for API credentials (base64 encoded)"
    )

    # Bots
    bots: list[BotConfig] = Field(default_factory=list, description="Bot configurations")

    class Config:
        json_schema_extra = {
            "example": {
                "database_url": "postgresql+asyncpg://user:pass@localhost/traderagent",
                "database_pool_size": 5,
                "log_level": "INFO",
                "log_to_file": True,
                "log_to_console": True,
                "json_logs": False,
                "encryption_key": "base64_encoded_key_here",
                "bots": [],
            }
        }
