"""Tests for GridStrategyConfig."""

from decimal import Decimal

import pytest

from grid_backtester.core.config import (
    GridRiskSchema,
    GridStrategyConfig,
    VolatilityMode,
    VOLATILITY_PRESETS,
)
from grid_backtester.core.calculator import GridConfig, GridSpacing
from grid_backtester.core.risk_manager import GridRiskConfig


class TestVolatilityPresets:

    def test_all_presets_exist(self):
        for mode in ["low", "medium", "high"]:
            assert mode in VOLATILITY_PRESETS
            preset = VOLATILITY_PRESETS[mode]
            assert "grid_spacing" in preset
            assert "num_levels" in preset
            assert "risk" in preset


class TestGridRiskSchema:

    def test_defaults(self):
        schema = GridRiskSchema()
        assert schema.max_open_orders == 25
        assert schema.grid_stop_loss_pct == Decimal("0.05")

    def test_to_risk_config(self):
        schema = GridRiskSchema()
        config = schema.to_risk_config()
        assert isinstance(config, GridRiskConfig)
        assert config.max_position_size == schema.max_position_size


class TestGridStrategyConfig:

    def test_basic_creation(self):
        config = GridStrategyConfig(symbol="BTCUSDT")
        assert config.symbol == "BTCUSDT"
        assert config.volatility_mode == VolatilityMode.MEDIUM
        assert config.num_levels == 15

    def test_invalid_price_bounds(self):
        with pytest.raises(ValueError):
            GridStrategyConfig(
                symbol="BTCUSDT",
                upper_price=Decimal("40000"),
                lower_price=Decimal("50000"),
            )

    def test_valid_price_bounds(self):
        config = GridStrategyConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
        )
        assert config.upper_price == Decimal("50000")

    def test_to_grid_config_with_bounds(self):
        config = GridStrategyConfig(
            symbol="BTCUSDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=10,
        )
        gc = config.to_grid_config()
        assert isinstance(gc, GridConfig)
        assert gc.num_levels == 10

    def test_to_grid_config_without_bounds(self):
        config = GridStrategyConfig(symbol="BTCUSDT")
        assert config.to_grid_config() is None

    def test_to_risk_config(self):
        config = GridStrategyConfig(symbol="BTCUSDT")
        rc = config.to_risk_config()
        assert isinstance(rc, GridRiskConfig)

    def test_from_preset_low(self):
        config = GridStrategyConfig.from_preset("BTCUSDT", VolatilityMode.LOW)
        assert config.volatility_mode == VolatilityMode.LOW
        assert config.num_levels == 20
        assert config.grid_spacing == "arithmetic"

    def test_from_preset_high(self):
        config = GridStrategyConfig.from_preset("BTCUSDT", VolatilityMode.HIGH)
        assert config.volatility_mode == VolatilityMode.HIGH
        assert config.grid_spacing == "geometric"
        assert config.num_levels == 10

    def test_from_preset_custom(self):
        config = GridStrategyConfig.from_preset(
            "BTCUSDT",
            VolatilityMode.CUSTOM,
            num_levels=25,
        )
        assert config.volatility_mode == VolatilityMode.CUSTOM
        assert config.num_levels == 25

    def test_from_preset_with_overrides(self):
        config = GridStrategyConfig.from_preset(
            "BTCUSDT",
            VolatilityMode.MEDIUM,
            num_levels=30,
        )
        assert config.num_levels == 30

    def test_yaml_roundtrip(self):
        original = GridStrategyConfig(
            symbol="ETHUSDT",
            volatility_mode=VolatilityMode.HIGH,
            num_levels=10,
            upper_price=Decimal("5000"),
            lower_price=Decimal("3000"),
        )
        yaml_str = original.to_yaml()
        loaded = GridStrategyConfig.from_yaml(yaml_str)
        assert loaded.symbol == original.symbol
        assert loaded.num_levels == original.num_levels

    def test_invalid_grid_spacing(self):
        with pytest.raises(ValueError):
            GridStrategyConfig(symbol="BTCUSDT", grid_spacing="invalid")

    def test_invalid_num_levels(self):
        with pytest.raises(ValueError):
            GridStrategyConfig(symbol="BTCUSDT", num_levels=1)
