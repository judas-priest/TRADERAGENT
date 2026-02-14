"""
DCA Strategy Configuration — v2.0 with market presets.

Provides YAML-compatible configuration for DCA strategy with:
- Market-based presets (conservative, moderate, aggressive)
- Signal, order, risk, and trailing stop config mapping
- Validation and serialization
"""

from decimal import Decimal
from enum import Enum
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from bot.strategies.dca.dca_signal_generator import DCASignalConfig, TrendDirection
from bot.strategies.dca.dca_position_manager import DCAOrderConfig
from bot.strategies.dca.dca_risk_manager import DCARiskConfig
from bot.strategies.dca.dca_trailing_stop import TrailingStopConfig, TrailingStopType
from bot.strategies.dca.dca_engine import FalseSignalFilter


# =============================================================================
# Market Presets
# =============================================================================


class MarketPreset(str, Enum):
    """Market regime for DCA configuration."""

    CONSERVATIVE = "conservative"  # Stable markets, tight parameters
    MODERATE = "moderate"  # BTC/ETH normal conditions
    AGGRESSIVE = "aggressive"  # Altcoins, volatile markets
    CUSTOM = "custom"  # User-defined


MARKET_PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "signal": {
            "trend_direction": "down",
            "min_trend_strength": 25.0,
            "require_confluence": True,
            "min_confluence_score": 0.7,
            "max_concurrent_deals": 2,
            "max_daily_loss": "300",
            "min_seconds_between_deals": 300,
        },
        "order": {
            "base_order_volume": "50",
            "max_safety_orders": 3,
            "volume_multiplier": "1.3",
            "price_step_pct": "1.5",
            "take_profit_pct": "2.0",
            "stop_loss_pct": "8.0",
            "max_position_cost": "3000",
        },
        "risk": {
            "max_concurrent_deals": 2,
            "max_total_exposure": "5000",
            "max_daily_loss": "300",
            "max_deal_drawdown_pct": "12.0",
            "max_portfolio_drawdown_pct": "5.0",
            "max_consecutive_losses": 5,
            "max_price_change_pct": "8.0",
            "min_balance_pct": "0.30",
        },
        "trailing": {
            "enabled": True,
            "activation_pct": "2.0",
            "distance_pct": "0.6",
            "stop_type": "percentage",
        },
        "filter": {
            "confirmation_count": 2,
            "min_rejection_cooldown": 60,
            "max_recent_price_change_pct": "3.0",
        },
    },
    "moderate": {
        "signal": {
            "trend_direction": "down",
            "min_trend_strength": 20.0,
            "require_confluence": True,
            "min_confluence_score": 0.6,
            "max_concurrent_deals": 3,
            "max_daily_loss": "500",
            "min_seconds_between_deals": 120,
        },
        "order": {
            "base_order_volume": "100",
            "max_safety_orders": 5,
            "volume_multiplier": "1.5",
            "price_step_pct": "2.0",
            "take_profit_pct": "3.0",
            "stop_loss_pct": "10.0",
            "max_position_cost": "5000",
        },
        "risk": {
            "max_concurrent_deals": 3,
            "max_total_exposure": "10000",
            "max_daily_loss": "500",
            "max_deal_drawdown_pct": "15.0",
            "max_portfolio_drawdown_pct": "10.0",
            "max_consecutive_losses": 4,
            "max_price_change_pct": "10.0",
            "min_balance_pct": "0.20",
        },
        "trailing": {
            "enabled": True,
            "activation_pct": "1.5",
            "distance_pct": "0.8",
            "stop_type": "percentage",
        },
        "filter": {
            "confirmation_count": 1,
            "min_rejection_cooldown": 30,
            "max_recent_price_change_pct": "5.0",
        },
    },
    "aggressive": {
        "signal": {
            "trend_direction": "down",
            "min_trend_strength": 15.0,
            "require_confluence": True,
            "min_confluence_score": 0.5,
            "max_concurrent_deals": 5,
            "max_daily_loss": "1000",
            "min_seconds_between_deals": 60,
        },
        "order": {
            "base_order_volume": "200",
            "max_safety_orders": 7,
            "volume_multiplier": "1.8",
            "price_step_pct": "3.0",
            "take_profit_pct": "5.0",
            "stop_loss_pct": "15.0",
            "max_position_cost": "15000",
        },
        "risk": {
            "max_concurrent_deals": 5,
            "max_total_exposure": "25000",
            "max_daily_loss": "1000",
            "max_deal_drawdown_pct": "20.0",
            "max_portfolio_drawdown_pct": "15.0",
            "max_consecutive_losses": 3,
            "max_price_change_pct": "15.0",
            "min_balance_pct": "0.15",
        },
        "trailing": {
            "enabled": True,
            "activation_pct": "2.5",
            "distance_pct": "1.0",
            "stop_type": "percentage",
        },
        "filter": {
            "confirmation_count": 1,
            "min_rejection_cooldown": 0,
            "max_recent_price_change_pct": "8.0",
        },
    },
}


# =============================================================================
# Pydantic Schemas
# =============================================================================


class DCASignalSchema(BaseModel):
    """Signal generator settings."""

    trend_direction: str = Field(default="down", pattern="^(down|up)$")
    min_trend_strength: float = Field(default=20.0, ge=0, le=100)
    entry_price_min: Decimal | None = Field(default=None, gt=0)
    entry_price_max: Decimal | None = Field(default=None, gt=0)
    require_confluence: bool = Field(default=True)
    min_confluence_score: float = Field(default=0.6, ge=0, le=1)
    max_concurrent_deals: int = Field(default=3, ge=1, le=20)
    max_daily_loss: Decimal = Field(default=Decimal("500"), gt=0)
    min_seconds_between_deals: int = Field(default=120, ge=0)

    def to_signal_config(self) -> DCASignalConfig:
        """Convert to DCASignalConfig dataclass."""
        return DCASignalConfig(
            trend_direction=TrendDirection(self.trend_direction),
            min_trend_strength=self.min_trend_strength,
            entry_price_min=self.entry_price_min,
            entry_price_max=self.entry_price_max,
            require_confluence=self.require_confluence,
            min_confluence_score=self.min_confluence_score,
            max_concurrent_deals=self.max_concurrent_deals,
            max_daily_loss=self.max_daily_loss,
            min_seconds_between_deals=self.min_seconds_between_deals,
        )


class DCAOrderSchema(BaseModel):
    """Order/position settings."""

    base_order_volume: Decimal = Field(default=Decimal("100"), gt=0)
    max_safety_orders: int = Field(default=5, ge=0, le=20)
    volume_multiplier: Decimal = Field(default=Decimal("1.5"), gt=0)
    price_step_pct: Decimal = Field(default=Decimal("2.0"), gt=0, le=50)
    take_profit_pct: Decimal = Field(default=Decimal("3.0"), gt=0, le=100)
    stop_loss_pct: Decimal = Field(default=Decimal("10.0"), gt=0, le=100)
    max_position_cost: Decimal = Field(default=Decimal("5000"), gt=0)

    def to_order_config(self) -> DCAOrderConfig:
        """Convert to DCAOrderConfig dataclass."""
        return DCAOrderConfig(
            base_order_volume=self.base_order_volume,
            max_safety_orders=self.max_safety_orders,
            volume_multiplier=self.volume_multiplier,
            price_step_pct=self.price_step_pct,
            take_profit_pct=self.take_profit_pct,
            stop_loss_pct=self.stop_loss_pct,
            max_position_cost=self.max_position_cost,
        )


class DCARiskSchema(BaseModel):
    """Risk management settings."""

    max_concurrent_deals: int = Field(default=3, ge=1, le=20)
    max_total_exposure: Decimal = Field(default=Decimal("10000"), gt=0)
    max_daily_loss: Decimal = Field(default=Decimal("500"), gt=0)
    max_deal_drawdown_pct: Decimal = Field(default=Decimal("15.0"), gt=0, le=100)
    max_portfolio_drawdown_pct: Decimal = Field(default=Decimal("10.0"), gt=0, le=100)
    max_consecutive_losses: int = Field(default=4, ge=1, le=20)
    max_price_change_pct: Decimal = Field(default=Decimal("10.0"), gt=0, le=100)
    min_balance_pct: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)

    def to_risk_config(self) -> DCARiskConfig:
        """Convert to DCARiskConfig dataclass."""
        return DCARiskConfig(
            max_concurrent_deals=self.max_concurrent_deals,
            max_total_exposure=self.max_total_exposure,
            max_daily_loss=self.max_daily_loss,
            max_deal_drawdown_pct=self.max_deal_drawdown_pct,
            max_portfolio_drawdown_pct=self.max_portfolio_drawdown_pct,
            max_consecutive_losses=self.max_consecutive_losses,
            max_price_change_pct=self.max_price_change_pct,
            min_balance_pct=self.min_balance_pct,
        )


class DCATrailingSchema(BaseModel):
    """Trailing stop settings."""

    enabled: bool = Field(default=True)
    activation_pct: Decimal = Field(default=Decimal("1.5"), ge=0)
    distance_pct: Decimal = Field(default=Decimal("0.8"), gt=0)
    distance_abs: Decimal = Field(default=Decimal("25"), gt=0)
    stop_type: str = Field(default="percentage", pattern="^(percentage|absolute)$")

    def to_trailing_config(self) -> TrailingStopConfig:
        """Convert to TrailingStopConfig dataclass."""
        return TrailingStopConfig(
            enabled=self.enabled,
            activation_pct=self.activation_pct,
            distance_pct=self.distance_pct,
            distance_abs=self.distance_abs,
            stop_type=TrailingStopType(self.stop_type),
        )


class DCAFilterSchema(BaseModel):
    """False signal filter settings."""

    confirmation_count: int = Field(default=1, ge=1, le=10)
    min_rejection_cooldown: int = Field(default=30, ge=0)
    max_recent_price_change_pct: Decimal = Field(default=Decimal("5.0"), gt=0)

    def to_filter(self) -> FalseSignalFilter:
        """Convert to FalseSignalFilter dataclass."""
        return FalseSignalFilter(
            confirmation_count=self.confirmation_count,
            min_rejection_cooldown=self.min_rejection_cooldown,
            max_recent_price_change_pct=self.max_recent_price_change_pct,
        )


# =============================================================================
# DCA Strategy Config
# =============================================================================


class DCAStrategyConfig(BaseModel):
    """
    Complete DCA strategy configuration (v2.0).

    Can be loaded from YAML with market presets or custom values.
    """

    # General
    symbol: str = Field(..., description="Trading pair (e.g., BTC/USDT)")
    market_preset: MarketPreset = Field(
        default=MarketPreset.MODERATE,
        description="Market regime preset",
    )

    # Component configs
    signal: DCASignalSchema = Field(default_factory=DCASignalSchema)
    order: DCAOrderSchema = Field(default_factory=DCAOrderSchema)
    risk: DCARiskSchema = Field(default_factory=DCARiskSchema)
    trailing: DCATrailingSchema = Field(default_factory=DCATrailingSchema)
    filter: DCAFilterSchema = Field(default_factory=DCAFilterSchema)

    # Operational
    dry_run: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_consistency(self) -> "DCAStrategyConfig":
        """Validate cross-field consistency."""
        if self.signal.max_concurrent_deals != self.risk.max_concurrent_deals:
            self.risk.max_concurrent_deals = self.signal.max_concurrent_deals
        if self.signal.max_daily_loss != self.risk.max_daily_loss:
            self.risk.max_daily_loss = self.signal.max_daily_loss
        return self

    def to_signal_config(self) -> DCASignalConfig:
        """Convert signal section to DCASignalConfig."""
        return self.signal.to_signal_config()

    def to_order_config(self) -> DCAOrderConfig:
        """Convert order section to DCAOrderConfig."""
        return self.order.to_order_config()

    def to_risk_config(self) -> DCARiskConfig:
        """Convert risk section to DCARiskConfig."""
        return self.risk.to_risk_config()

    def to_trailing_config(self) -> TrailingStopConfig:
        """Convert trailing section to TrailingStopConfig."""
        return self.trailing.to_trailing_config()

    def to_filter(self) -> FalseSignalFilter:
        """Convert filter section to FalseSignalFilter."""
        return self.filter.to_filter()

    @classmethod
    def from_preset(
        cls, symbol: str, preset: MarketPreset, **overrides: Any
    ) -> "DCAStrategyConfig":
        """
        Create config from a market preset with optional overrides.

        Args:
            symbol: Trading pair.
            preset: Market preset.
            **overrides: Override any preset value.

        Returns:
            DCAStrategyConfig instance.
        """
        if preset == MarketPreset.CUSTOM:
            return cls(symbol=symbol, market_preset=preset, **overrides)

        preset_data = MARKET_PRESETS[preset.value]
        sections: dict[str, Any] = {}

        for section_name in ("signal", "order", "risk", "trailing", "filter"):
            section_preset = preset_data.get(section_name, {}).copy()
            section_override = overrides.pop(section_name, {})
            if isinstance(section_override, dict):
                section_preset.update(section_override)
            sections[section_name] = section_preset

        return cls(
            symbol=symbol,
            market_preset=preset,
            **sections,
            **overrides,
        )

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        data = self.model_dump(mode="json")
        return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "DCAStrategyConfig":
        """Load from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls(**data)

    @classmethod
    def from_yaml_file(cls, path: str) -> "DCAStrategyConfig":
        """Load from YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)
