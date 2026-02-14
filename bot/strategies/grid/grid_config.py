"""
Grid Strategy Configuration — v2.0 with volatility presets.

Provides YAML-compatible configuration for grid strategy with:
- Volatility-based presets (low, medium, high)
- Grid calculator config mapping
- Risk manager config mapping
- Validation and serialization
"""

from decimal import Decimal
from enum import Enum
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from bot.strategies.grid.grid_calculator import GridConfig, GridSpacing
from bot.strategies.grid.grid_risk_manager import GridRiskConfig


# =============================================================================
# Volatility Presets
# =============================================================================


class VolatilityMode(str, Enum):
    """Volatility regime for grid configuration."""

    LOW = "low"  # Stablecoins, tight range
    MEDIUM = "medium"  # BTC/ETH normal conditions
    HIGH = "high"  # Altcoins, high volatility
    CUSTOM = "custom"  # User-defined


# Pre-defined configurations for each volatility mode
VOLATILITY_PRESETS: dict[str, dict[str, Any]] = {
    "low": {
        "grid_spacing": "arithmetic",
        "num_levels": 20,
        "amount_per_grid": "50",
        "profit_per_grid": "0.002",  # 0.2%
        "atr_multiplier": "1.5",
        "risk": {
            "max_position_size": "500",
            "max_total_exposure": "5000",
            "max_open_orders": 30,
            "grid_stop_loss_pct": "0.03",
            "max_unrealized_loss": "200",
            "max_drawdown_pct": "0.05",
            "max_consecutive_losses": 8,
            "trend_atr_multiplier": "3.0",
            "trend_adx_threshold": 30.0,
            "min_balance_pct": "0.30",
        },
    },
    "medium": {
        "grid_spacing": "arithmetic",
        "num_levels": 15,
        "amount_per_grid": "100",
        "profit_per_grid": "0.005",  # 0.5%
        "atr_multiplier": "3.0",
        "risk": {
            "max_position_size": "1000",
            "max_total_exposure": "10000",
            "max_open_orders": 25,
            "grid_stop_loss_pct": "0.05",
            "max_unrealized_loss": "500",
            "max_drawdown_pct": "0.10",
            "max_consecutive_losses": 5,
            "trend_atr_multiplier": "2.0",
            "trend_adx_threshold": 25.0,
            "min_balance_pct": "0.20",
        },
    },
    "high": {
        "grid_spacing": "geometric",
        "num_levels": 10,
        "amount_per_grid": "200",
        "profit_per_grid": "0.01",  # 1%
        "atr_multiplier": "4.0",
        "risk": {
            "max_position_size": "2000",
            "max_total_exposure": "15000",
            "max_open_orders": 20,
            "grid_stop_loss_pct": "0.08",
            "max_unrealized_loss": "1000",
            "max_drawdown_pct": "0.15",
            "max_consecutive_losses": 3,
            "trend_atr_multiplier": "1.5",
            "trend_adx_threshold": 20.0,
            "min_balance_pct": "0.25",
        },
    },
}


# =============================================================================
# Pydantic Config Schemas (v2.0)
# =============================================================================


class GridRiskSchema(BaseModel):
    """Risk management settings for grid strategy."""

    max_position_size: Decimal = Field(default=Decimal("1000"), gt=0)
    max_total_exposure: Decimal = Field(default=Decimal("10000"), gt=0)
    max_open_orders: int = Field(default=25, ge=1, le=100)
    grid_stop_loss_pct: Decimal = Field(default=Decimal("0.05"), gt=0, le=1)
    max_unrealized_loss: Decimal = Field(default=Decimal("500"), gt=0)
    max_drawdown_pct: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    max_consecutive_losses: int = Field(default=5, ge=1, le=20)
    trend_atr_multiplier: Decimal = Field(default=Decimal("2.0"), gt=0)
    trend_adx_threshold: float = Field(default=25.0, gt=0, le=100)
    min_balance_pct: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)

    def to_risk_config(self) -> GridRiskConfig:
        """Convert to GridRiskConfig dataclass."""
        return GridRiskConfig(
            max_position_size=self.max_position_size,
            max_total_exposure=self.max_total_exposure,
            max_open_orders=self.max_open_orders,
            grid_stop_loss_pct=self.grid_stop_loss_pct,
            max_unrealized_loss=self.max_unrealized_loss,
            max_drawdown_pct=self.max_drawdown_pct,
            max_consecutive_losses=self.max_consecutive_losses,
            trend_atr_multiplier=self.trend_atr_multiplier,
            trend_adx_threshold=self.trend_adx_threshold,
            min_balance_pct=self.min_balance_pct,
        )


class GridStrategyConfig(BaseModel):
    """
    Complete grid strategy configuration (v2.0).

    Can be loaded from YAML with volatility presets or custom values.
    """

    # General
    symbol: str = Field(..., description="Trading pair (e.g., BTC/USDT)")
    volatility_mode: VolatilityMode = Field(
        default=VolatilityMode.MEDIUM,
        description="Volatility regime preset",
    )

    # Grid parameters (overridable)
    grid_spacing: str = Field(default="arithmetic", pattern="^(arithmetic|geometric)$")
    num_levels: int = Field(default=15, ge=2, le=100)
    amount_per_grid: Decimal = Field(default=Decimal("100"), gt=0)
    profit_per_grid: Decimal = Field(default=Decimal("0.005"), ge=0, le=1)
    atr_multiplier: Decimal = Field(default=Decimal("3.0"), gt=0)
    atr_period: int = Field(default=14, ge=1, le=100)

    # Optional fixed bounds (if not using ATR)
    upper_price: Decimal | None = Field(default=None, gt=0)
    lower_price: Decimal | None = Field(default=None, gt=0)

    # Risk
    risk: GridRiskSchema = Field(default_factory=GridRiskSchema)

    # Operational
    dry_run: bool = Field(default=False)
    auto_rebalance: bool = Field(default=True)
    rebalance_threshold_pct: Decimal = Field(
        default=Decimal("0.02"), ge=0, le=1,
        description="Rebalance when price moves this % outside grid",
    )

    @model_validator(mode="after")
    def validate_price_bounds(self) -> "GridStrategyConfig":
        """If fixed bounds given, upper must be > lower."""
        if self.upper_price is not None and self.lower_price is not None:
            if self.upper_price <= self.lower_price:
                raise ValueError("upper_price must be greater than lower_price")
        return self

    def to_grid_config(self) -> GridConfig | None:
        """
        Convert to GridConfig for GridCalculator.

        Returns None if fixed bounds are not set (ATR mode needed).
        """
        if self.upper_price is None or self.lower_price is None:
            return None
        return GridConfig(
            upper_price=self.upper_price,
            lower_price=self.lower_price,
            num_levels=self.num_levels,
            spacing=GridSpacing(self.grid_spacing),
            amount_per_grid=self.amount_per_grid,
            profit_per_grid=self.profit_per_grid,
        )

    def to_risk_config(self) -> GridRiskConfig:
        """Convert risk section to GridRiskConfig."""
        return self.risk.to_risk_config()

    @classmethod
    def from_preset(cls, symbol: str, mode: VolatilityMode, **overrides: Any) -> "GridStrategyConfig":
        """
        Create config from a volatility preset with optional overrides.

        Args:
            symbol: Trading pair.
            mode: Volatility mode.
            **overrides: Override any preset value.

        Returns:
            GridStrategyConfig instance.
        """
        if mode == VolatilityMode.CUSTOM:
            return cls(symbol=symbol, volatility_mode=mode, **overrides)

        preset = VOLATILITY_PRESETS[mode.value].copy()
        risk_preset = preset.pop("risk", {})

        # Apply overrides
        for key, value in overrides.items():
            if key == "risk" and isinstance(value, dict):
                risk_preset.update(value)
            else:
                preset[key] = value

        return cls(
            symbol=symbol,
            volatility_mode=mode,
            risk=GridRiskSchema(**risk_preset),
            **preset,
        )

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        data = self.model_dump(mode="json")
        return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "GridStrategyConfig":
        """Load from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls(**data)

    @classmethod
    def from_yaml_file(cls, path: str) -> "GridStrategyConfig":
        """Load from YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)
