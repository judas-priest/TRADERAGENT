"""Tests for Grid Strategy Configuration v2.0.

Tests volatility presets, YAML serialization, and config-to-component mapping.
"""

from decimal import Decimal

import pytest
import yaml

from bot.strategies.grid.grid_calculator import GridSpacing
from bot.strategies.grid.grid_config import (
    VOLATILITY_PRESETS,
    GridRiskSchema,
    GridStrategyConfig,
    VolatilityMode,
)
from bot.strategies.grid.grid_risk_manager import GridRiskConfig

# =========================================================================
# Volatility Presets Tests
# =========================================================================


class TestVolatilityPresets:
    def test_all_presets_exist(self):
        assert "low" in VOLATILITY_PRESETS
        assert "medium" in VOLATILITY_PRESETS
        assert "high" in VOLATILITY_PRESETS

    def test_low_preset(self):
        cfg = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.LOW)
        assert cfg.num_levels == 20
        assert cfg.profit_per_grid == Decimal("0.002")
        assert cfg.grid_spacing == "arithmetic"
        assert cfg.risk.grid_stop_loss_pct == Decimal("0.03")

    def test_medium_preset(self):
        cfg = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.MEDIUM)
        assert cfg.num_levels == 15
        assert cfg.profit_per_grid == Decimal("0.005")
        assert cfg.risk.max_total_exposure == Decimal("10000")

    def test_high_preset(self):
        cfg = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.HIGH)
        assert cfg.num_levels == 10
        assert cfg.profit_per_grid == Decimal("0.01")
        assert cfg.grid_spacing == "geometric"
        assert cfg.risk.max_drawdown_pct == Decimal("0.15")

    def test_preset_with_overrides(self):
        cfg = GridStrategyConfig.from_preset(
            "ETH/USDT",
            VolatilityMode.MEDIUM,
            num_levels=25,
            profit_per_grid="0.008",
        )
        assert cfg.num_levels == 25
        assert cfg.profit_per_grid == Decimal("0.008")
        # Other values from preset
        assert cfg.amount_per_grid == Decimal("100")

    def test_preset_with_risk_override(self):
        cfg = GridStrategyConfig.from_preset(
            "BTC/USDT",
            VolatilityMode.MEDIUM,
            risk={"max_position_size": "2000"},
        )
        assert cfg.risk.max_position_size == Decimal("2000")
        # Other risk values from preset
        assert cfg.risk.max_open_orders == 25

    def test_custom_mode(self):
        cfg = GridStrategyConfig.from_preset(
            "BTC/USDT",
            VolatilityMode.CUSTOM,
            num_levels=30,
            amount_per_grid="500",
        )
        assert cfg.volatility_mode == VolatilityMode.CUSTOM
        assert cfg.num_levels == 30


# =========================================================================
# GridStrategyConfig Tests
# =========================================================================


class TestGridStrategyConfig:
    def test_defaults(self):
        cfg = GridStrategyConfig(symbol="BTC/USDT")
        assert cfg.volatility_mode == VolatilityMode.MEDIUM
        assert cfg.grid_spacing == "arithmetic"
        assert cfg.dry_run is False
        assert cfg.auto_rebalance is True

    def test_with_fixed_bounds(self):
        cfg = GridStrategyConfig(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
        )
        assert cfg.upper_price == Decimal("50000")
        assert cfg.lower_price == Decimal("40000")

    def test_invalid_price_bounds(self):
        with pytest.raises(ValueError, match="upper_price must be greater"):
            GridStrategyConfig(
                symbol="BTC/USDT",
                upper_price=Decimal("40000"),
                lower_price=Decimal("50000"),
            )

    def test_to_grid_config_fixed_bounds(self):
        cfg = GridStrategyConfig(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=11,
            grid_spacing="geometric",
        )
        gc = cfg.to_grid_config()
        assert gc is not None
        assert gc.upper_price == Decimal("50000")
        assert gc.lower_price == Decimal("40000")
        assert gc.num_levels == 11
        assert gc.spacing == GridSpacing.GEOMETRIC

    def test_to_grid_config_no_bounds(self):
        cfg = GridStrategyConfig(symbol="BTC/USDT")
        assert cfg.to_grid_config() is None  # ATR mode

    def test_to_risk_config(self):
        cfg = GridStrategyConfig(symbol="BTC/USDT")
        rc = cfg.to_risk_config()
        assert isinstance(rc, GridRiskConfig)
        assert rc.max_position_size == Decimal("1000")

    def test_invalid_grid_spacing(self):
        with pytest.raises(ValueError):
            GridStrategyConfig(symbol="BTC/USDT", grid_spacing="linear")


# =========================================================================
# YAML Serialization Tests
# =========================================================================


class TestYAMLSerialization:
    def test_to_yaml(self):
        cfg = GridStrategyConfig(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
        )
        yaml_str = cfg.to_yaml()
        assert "BTC/USDT" in yaml_str
        assert "50000" in yaml_str

    def test_from_yaml_roundtrip(self):
        original = GridStrategyConfig.from_preset("ETH/USDT", VolatilityMode.HIGH)
        yaml_str = original.to_yaml()
        loaded = GridStrategyConfig.from_yaml(yaml_str)
        assert loaded.symbol == "ETH/USDT"
        assert loaded.volatility_mode == VolatilityMode.HIGH
        assert loaded.num_levels == original.num_levels
        assert loaded.profit_per_grid == original.profit_per_grid

    def test_from_yaml_file(self, tmp_path):
        cfg = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.LOW)
        file_path = tmp_path / "grid_config.yaml"
        file_path.write_text(cfg.to_yaml())

        loaded = GridStrategyConfig.from_yaml_file(str(file_path))
        assert loaded.symbol == "BTC/USDT"
        assert loaded.num_levels == 20

    def test_yaml_includes_all_fields(self):
        cfg = GridStrategyConfig(symbol="BTC/USDT")
        data = yaml.safe_load(cfg.to_yaml())
        assert "symbol" in data
        assert "volatility_mode" in data
        assert "grid_spacing" in data
        assert "risk" in data
        assert "dry_run" in data

    def test_preset_yaml_roundtrip_all_modes(self):
        for mode in [VolatilityMode.LOW, VolatilityMode.MEDIUM, VolatilityMode.HIGH]:
            cfg = GridStrategyConfig.from_preset("BTC/USDT", mode)
            yaml_str = cfg.to_yaml()
            loaded = GridStrategyConfig.from_yaml(yaml_str)
            assert loaded.volatility_mode == mode
            assert loaded.num_levels == cfg.num_levels


# =========================================================================
# GridRiskSchema Tests
# =========================================================================


class TestGridRiskSchema:
    def test_defaults(self):
        schema = GridRiskSchema()
        assert schema.max_position_size == Decimal("1000")
        assert schema.trend_adx_threshold == 25.0

    def test_to_risk_config(self):
        schema = GridRiskSchema(max_position_size=Decimal("2000"))
        rc = schema.to_risk_config()
        assert isinstance(rc, GridRiskConfig)
        assert rc.max_position_size == Decimal("2000")
