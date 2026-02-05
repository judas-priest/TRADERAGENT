"""Tests for configuration schemas"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from bot.config.schemas import (
    BotConfig,
    DCAConfig,
    ExchangeConfig,
    GridConfig,
    RiskManagementConfig,
    StrategyType,
)


class TestExchangeConfig:
    """Test ExchangeConfig validation"""

    def test_valid_exchange_config(self):
        """Test valid exchange configuration"""
        config = ExchangeConfig(
            exchange_id="binance",
            credentials_name="test_creds",
            sandbox=True,
        )
        assert config.exchange_id == "binance"
        assert config.sandbox is True

    def test_missing_required_fields(self):
        """Test missing required fields"""
        with pytest.raises(ValidationError):
            ExchangeConfig()


class TestGridConfig:
    """Test GridConfig validation"""

    def test_valid_grid_config(self):
        """Test valid grid configuration"""
        config = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=10,
            amount_per_grid=Decimal("100"),
        )
        assert config.upper_price == Decimal("50000")
        assert config.grid_levels == 10

    def test_upper_price_validation(self):
        """Test upper price must be greater than lower price"""
        with pytest.raises(ValidationError):
            GridConfig(
                upper_price=Decimal("40000"),
                lower_price=Decimal("50000"),  # Lower is higher!
                grid_levels=10,
                amount_per_grid=Decimal("100"),
            )

    def test_grid_levels_range(self):
        """Test grid levels must be in valid range"""
        # Too few levels
        with pytest.raises(ValidationError):
            GridConfig(
                upper_price=Decimal("50000"),
                lower_price=Decimal("40000"),
                grid_levels=1,  # Less than 2
                amount_per_grid=Decimal("100"),
            )

        # Too many levels
        with pytest.raises(ValidationError):
            GridConfig(
                upper_price=Decimal("50000"),
                lower_price=Decimal("40000"),
                grid_levels=101,  # More than 100
                amount_per_grid=Decimal("100"),
            )


class TestDCAConfig:
    """Test DCAConfig validation"""

    def test_valid_dca_config(self):
        """Test valid DCA configuration"""
        config = DCAConfig(
            amount_per_step=Decimal("100"),
            max_steps=5,
        )
        assert config.amount_per_step == Decimal("100")
        assert config.max_steps == 5

    def test_max_steps_range(self):
        """Test max steps must be in valid range"""
        with pytest.raises(ValidationError):
            DCAConfig(
                amount_per_step=Decimal("100"),
                max_steps=0,  # Less than 1
            )

        with pytest.raises(ValidationError):
            DCAConfig(
                amount_per_step=Decimal("100"),
                max_steps=21,  # More than 20
            )


class TestRiskManagementConfig:
    """Test RiskManagementConfig validation"""

    def test_valid_risk_config(self):
        """Test valid risk management configuration"""
        config = RiskManagementConfig(
            max_position_size=Decimal("10000"),
            stop_loss_percentage=Decimal("0.15"),
            min_order_size=Decimal("10"),
        )
        assert config.max_position_size == Decimal("10000")
        assert config.stop_loss_percentage == Decimal("0.15")

    def test_optional_fields(self):
        """Test optional fields"""
        config = RiskManagementConfig(
            max_position_size=Decimal("10000"),
        )
        assert config.stop_loss_percentage is None
        assert config.max_daily_loss is None


class TestBotConfig:
    """Test BotConfig validation"""

    def test_valid_grid_bot_config(self):
        """Test valid grid bot configuration"""
        config = BotConfig(
            name="test_bot",
            symbol="BTC/USDT",
            strategy=StrategyType.GRID,
            exchange=ExchangeConfig(
                exchange_id="binance",
                credentials_name="test",
            ),
            grid=GridConfig(
                upper_price=Decimal("50000"),
                lower_price=Decimal("40000"),
                grid_levels=10,
                amount_per_grid=Decimal("100"),
            ),
            risk_management=RiskManagementConfig(
                max_position_size=Decimal("10000"),
            ),
        )
        assert config.name == "test_bot"
        assert config.strategy == StrategyType.GRID

    def test_valid_dca_bot_config(self):
        """Test valid DCA bot configuration"""
        config = BotConfig(
            name="dca_bot",
            symbol="ETH/USDT",
            strategy=StrategyType.DCA,
            exchange=ExchangeConfig(
                exchange_id="binance",
                credentials_name="test",
            ),
            dca=DCAConfig(
                amount_per_step=Decimal("100"),
                max_steps=5,
            ),
            risk_management=RiskManagementConfig(
                max_position_size=Decimal("5000"),
            ),
        )
        assert config.strategy == StrategyType.DCA

    def test_valid_hybrid_bot_config(self):
        """Test valid hybrid bot configuration"""
        config = BotConfig(
            name="hybrid_bot",
            symbol="BTC/USDT",
            strategy=StrategyType.HYBRID,
            exchange=ExchangeConfig(
                exchange_id="binance",
                credentials_name="test",
            ),
            grid=GridConfig(
                upper_price=Decimal("50000"),
                lower_price=Decimal("40000"),
                grid_levels=10,
                amount_per_grid=Decimal("100"),
            ),
            dca=DCAConfig(
                amount_per_step=Decimal("100"),
                max_steps=5,
            ),
            risk_management=RiskManagementConfig(
                max_position_size=Decimal("10000"),
            ),
        )
        assert config.strategy == StrategyType.HYBRID

    def test_grid_strategy_requires_grid_config(self):
        """Test grid strategy requires grid configuration"""
        with pytest.raises(ValidationError):
            BotConfig(
                name="test_bot",
                symbol="BTC/USDT",
                strategy=StrategyType.GRID,
                exchange=ExchangeConfig(
                    exchange_id="binance",
                    credentials_name="test",
                ),
                # Missing grid config!
                risk_management=RiskManagementConfig(
                    max_position_size=Decimal("10000"),
                ),
            )

    def test_dca_strategy_requires_dca_config(self):
        """Test DCA strategy requires DCA configuration"""
        with pytest.raises(ValidationError):
            BotConfig(
                name="test_bot",
                symbol="BTC/USDT",
                strategy=StrategyType.DCA,
                exchange=ExchangeConfig(
                    exchange_id="binance",
                    credentials_name="test",
                ),
                # Missing dca config!
                risk_management=RiskManagementConfig(
                    max_position_size=Decimal("10000"),
                ),
            )

    def test_hybrid_strategy_requires_both_configs(self):
        """Test hybrid strategy requires both grid and DCA configs"""
        # Missing grid
        with pytest.raises(ValidationError):
            BotConfig(
                name="test_bot",
                symbol="BTC/USDT",
                strategy=StrategyType.HYBRID,
                exchange=ExchangeConfig(
                    exchange_id="binance",
                    credentials_name="test",
                ),
                dca=DCAConfig(
                    amount_per_step=Decimal("100"),
                    max_steps=5,
                ),
                risk_management=RiskManagementConfig(
                    max_position_size=Decimal("10000"),
                ),
            )

        # Missing DCA
        with pytest.raises(ValidationError):
            BotConfig(
                name="test_bot",
                symbol="BTC/USDT",
                strategy=StrategyType.HYBRID,
                exchange=ExchangeConfig(
                    exchange_id="binance",
                    credentials_name="test",
                ),
                grid=GridConfig(
                    upper_price=Decimal("50000"),
                    lower_price=Decimal("40000"),
                    grid_levels=10,
                    amount_per_grid=Decimal("100"),
                ),
                risk_management=RiskManagementConfig(
                    max_position_size=Decimal("10000"),
                ),
            )
