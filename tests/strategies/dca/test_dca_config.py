"""Tests for DCA Strategy Configuration v2.0.

Tests market presets, YAML serialization, config-to-component mapping,
integration tests with mock exchange, and backtesting comparison.
"""

from decimal import Decimal

import pytest
import yaml

from bot.strategies.dca.dca_backtester import (
    BacktestResult,
    BacktestTrade,
    DCABacktester,
    compare_strategies,
)
from bot.strategies.dca.dca_config import (
    MARKET_PRESETS,
    DCAFilterSchema,
    DCAOrderSchema,
    DCARiskSchema,
    DCASignalSchema,
    DCAStrategyConfig,
    DCATrailingSchema,
    MarketPreset,
)
from bot.strategies.dca.dca_engine import DCAEngine, FalseSignalFilter
from bot.strategies.dca.dca_position_manager import DCAOrderConfig
from bot.strategies.dca.dca_risk_manager import DCARiskConfig
from bot.strategies.dca.dca_signal_generator import (
    DCASignalConfig,
    MarketState,
    TrendDirection,
)
from bot.strategies.dca.dca_trailing_stop import TrailingStopConfig, TrailingStopType

# =========================================================================
# Market Presets Tests
# =========================================================================


class TestMarketPresets:
    def test_all_presets_exist(self):
        assert "conservative" in MARKET_PRESETS
        assert "moderate" in MARKET_PRESETS
        assert "aggressive" in MARKET_PRESETS

    def test_conservative_preset(self):
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.CONSERVATIVE)
        assert cfg.signal.min_confluence_score == 0.7
        assert cfg.order.base_order_volume == Decimal("50")
        assert cfg.order.max_safety_orders == 3
        assert cfg.risk.max_concurrent_deals == 2
        assert cfg.trailing.activation_pct == Decimal("2.0")
        assert cfg.filter.confirmation_count == 2

    def test_moderate_preset(self):
        cfg = DCAStrategyConfig.from_preset("ETH/USDT", MarketPreset.MODERATE)
        assert cfg.signal.min_confluence_score == 0.6
        assert cfg.order.base_order_volume == Decimal("100")
        assert cfg.order.max_safety_orders == 5
        assert cfg.risk.max_concurrent_deals == 3
        assert cfg.trailing.activation_pct == Decimal("1.5")

    def test_aggressive_preset(self):
        cfg = DCAStrategyConfig.from_preset("DOGE/USDT", MarketPreset.AGGRESSIVE)
        assert cfg.signal.min_confluence_score == 0.5
        assert cfg.order.base_order_volume == Decimal("200")
        assert cfg.order.max_safety_orders == 7
        assert cfg.risk.max_concurrent_deals == 5
        assert cfg.trailing.activation_pct == Decimal("2.5")

    def test_preset_with_overrides(self):
        cfg = DCAStrategyConfig.from_preset(
            "BTC/USDT",
            MarketPreset.MODERATE,
            order={"base_order_volume": "250", "max_safety_orders": 8},
        )
        assert cfg.order.base_order_volume == Decimal("250")
        assert cfg.order.max_safety_orders == 8
        # Other values from preset
        assert cfg.order.price_step_pct == Decimal("2.0")

    def test_preset_with_risk_override(self):
        cfg = DCAStrategyConfig.from_preset(
            "BTC/USDT",
            MarketPreset.CONSERVATIVE,
            risk={"max_total_exposure": "20000"},
        )
        assert cfg.risk.max_total_exposure == Decimal("20000")
        # Other risk values from preset
        assert cfg.risk.max_portfolio_drawdown_pct == Decimal("5.0")

    def test_custom_mode(self):
        cfg = DCAStrategyConfig.from_preset(
            "BTC/USDT",
            MarketPreset.CUSTOM,
            order={"base_order_volume": "500", "max_safety_orders": 10},
        )
        assert cfg.market_preset == MarketPreset.CUSTOM
        assert cfg.order.base_order_volume == Decimal("500")

    def test_preset_sections_complete(self):
        for name, preset in MARKET_PRESETS.items():
            assert "signal" in preset, f"{name} missing signal"
            assert "order" in preset, f"{name} missing order"
            assert "risk" in preset, f"{name} missing risk"
            assert "trailing" in preset, f"{name} missing trailing"
            assert "filter" in preset, f"{name} missing filter"


# =========================================================================
# DCAStrategyConfig Tests
# =========================================================================


class TestDCAStrategyConfig:
    def test_defaults(self):
        cfg = DCAStrategyConfig(symbol="BTC/USDT")
        assert cfg.market_preset == MarketPreset.MODERATE
        assert cfg.dry_run is False

    def test_consistency_validator(self):
        cfg = DCAStrategyConfig(
            symbol="BTC/USDT",
            signal=DCASignalSchema(max_concurrent_deals=5, max_daily_loss=Decimal("800")),
            risk=DCARiskSchema(max_concurrent_deals=3, max_daily_loss=Decimal("500")),
        )
        # Validator syncs risk to signal values
        assert cfg.risk.max_concurrent_deals == 5
        assert cfg.risk.max_daily_loss == Decimal("800")

    def test_to_signal_config(self):
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.MODERATE)
        sc = cfg.to_signal_config()
        assert isinstance(sc, DCASignalConfig)
        assert sc.trend_direction == TrendDirection.DOWN
        assert sc.min_trend_strength == 20.0

    def test_to_order_config(self):
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.MODERATE)
        oc = cfg.to_order_config()
        assert isinstance(oc, DCAOrderConfig)
        assert oc.base_order_volume == Decimal("100")
        assert oc.max_safety_orders == 5

    def test_to_risk_config(self):
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.MODERATE)
        rc = cfg.to_risk_config()
        assert isinstance(rc, DCARiskConfig)
        assert rc.max_total_exposure == Decimal("10000")
        assert rc.max_deal_drawdown_pct == Decimal("15.0")

    def test_to_trailing_config(self):
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.MODERATE)
        tc = cfg.to_trailing_config()
        assert isinstance(tc, TrailingStopConfig)
        assert tc.enabled is True
        assert tc.activation_pct == Decimal("1.5")

    def test_to_filter(self):
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.MODERATE)
        flt = cfg.to_filter()
        assert isinstance(flt, FalseSignalFilter)
        assert flt.confirmation_count == 1


# =========================================================================
# YAML Serialization Tests
# =========================================================================


class TestYAMLSerialization:
    def test_to_yaml(self):
        cfg = DCAStrategyConfig(symbol="BTC/USDT")
        yaml_str = cfg.to_yaml()
        assert "BTC/USDT" in yaml_str
        assert "signal" in yaml_str
        assert "order" in yaml_str
        assert "risk" in yaml_str
        assert "trailing" in yaml_str

    def test_from_yaml_roundtrip(self):
        original = DCAStrategyConfig.from_preset("ETH/USDT", MarketPreset.AGGRESSIVE)
        yaml_str = original.to_yaml()
        loaded = DCAStrategyConfig.from_yaml(yaml_str)
        assert loaded.symbol == "ETH/USDT"
        assert loaded.order.base_order_volume == original.order.base_order_volume
        assert loaded.trailing.activation_pct == original.trailing.activation_pct

    def test_from_yaml_file(self, tmp_path):
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.CONSERVATIVE)
        file_path = tmp_path / "dca_config.yaml"
        file_path.write_text(cfg.to_yaml())

        loaded = DCAStrategyConfig.from_yaml_file(str(file_path))
        assert loaded.symbol == "BTC/USDT"
        assert loaded.order.max_safety_orders == 3

    def test_yaml_includes_all_fields(self):
        cfg = DCAStrategyConfig(symbol="BTC/USDT")
        data = yaml.safe_load(cfg.to_yaml())
        assert "symbol" in data
        assert "market_preset" in data
        assert "signal" in data
        assert "order" in data
        assert "risk" in data
        assert "trailing" in data
        assert "filter" in data
        assert "dry_run" in data

    def test_preset_yaml_roundtrip_all_modes(self):
        for preset in [MarketPreset.CONSERVATIVE, MarketPreset.MODERATE, MarketPreset.AGGRESSIVE]:
            cfg = DCAStrategyConfig.from_preset("BTC/USDT", preset)
            yaml_str = cfg.to_yaml()
            loaded = DCAStrategyConfig.from_yaml(yaml_str)
            assert loaded.order.base_order_volume == cfg.order.base_order_volume
            assert loaded.trailing.activation_pct == cfg.trailing.activation_pct


# =========================================================================
# Schema Tests
# =========================================================================


class TestSchemas:
    def test_signal_schema_defaults(self):
        s = DCASignalSchema()
        assert s.trend_direction == "down"
        assert s.min_trend_strength == 20.0

    def test_signal_schema_to_config(self):
        s = DCASignalSchema(trend_direction="up", min_trend_strength=30.0)
        sc = s.to_signal_config()
        assert sc.trend_direction == TrendDirection.UP
        assert sc.min_trend_strength == 30.0

    def test_order_schema_defaults(self):
        o = DCAOrderSchema()
        assert o.base_order_volume == Decimal("100")
        assert o.max_safety_orders == 5

    def test_risk_schema_to_config(self):
        r = DCARiskSchema(
            max_total_exposure=Decimal("20000"), max_deal_drawdown_pct=Decimal("18.0")
        )
        rc = r.to_risk_config()
        assert isinstance(rc, DCARiskConfig)
        assert rc.max_total_exposure == Decimal("20000")
        assert rc.max_deal_drawdown_pct == Decimal("18.0")

    def test_trailing_schema_absolute_type(self):
        t = DCATrailingSchema(stop_type="absolute", distance_abs=Decimal("50"))
        tc = t.to_trailing_config()
        assert tc.stop_type == TrailingStopType.ABSOLUTE
        assert tc.distance_abs == Decimal("50")

    def test_filter_schema_defaults(self):
        f = DCAFilterSchema()
        assert f.confirmation_count == 1
        assert f.min_rejection_cooldown == 30

    def test_invalid_trend_direction(self):
        with pytest.raises(ValueError):
            DCASignalSchema(trend_direction="sideways")

    def test_invalid_stop_type(self):
        with pytest.raises(ValueError):
            DCATrailingSchema(stop_type="invalid")


# =========================================================================
# Integration Tests — Full Engine from Config
# =========================================================================


class TestIntegrationFromConfig:
    def test_engine_from_config(self):
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.MODERATE)
        engine = DCAEngine(
            symbol=cfg.symbol,
            signal_config=cfg.to_signal_config(),
            order_config=cfg.to_order_config(),
            risk_config=cfg.to_risk_config(),
            trailing_config=cfg.to_trailing_config(),
            false_signal_filter=cfg.to_filter(),
        )
        assert engine.symbol == "BTC/USDT"
        stats = engine.get_statistics()
        assert stats["symbol"] == "BTC/USDT"

    def test_full_cycle_from_config(self):
        """Integration: config → engine → open → monitor → close."""
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.MODERATE)
        engine = DCAEngine(
            symbol=cfg.symbol,
            signal_config=cfg.to_signal_config(),
            order_config=cfg.to_order_config(),
            risk_config=cfg.to_risk_config(),
            trailing_config=cfg.to_trailing_config(),
            false_signal_filter=cfg.to_filter(),
        )

        # Open deal
        deal = engine.open_deal(Decimal("3100"))
        assert deal.symbol == "BTC/USDT"

        # Price rises past activation (1.5% = 3146.5) and trailing
        for price in [3150, 3200, 3300, 3400]:
            state = MarketState(current_price=Decimal(str(price)))
            engine.on_price_update(
                state,
                available_balance=Decimal("5000"),
                total_balance=Decimal("10000"),
            )

        # Drop below trailing stop (3400 * 0.992 = 3372.8)
        state = MarketState(current_price=Decimal("3370"))
        action = engine.on_price_update(
            state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert len(action.deals_to_close) == 1
        assert action.deals_to_close[0].reason == "trailing_stop"

        # Close and verify profit
        result = engine.close_deal(deal.id, Decimal("3370"), "trailing_stop")
        assert result.realized_profit > 0

    def test_conservative_blocks_more_deals(self):
        """Conservative preset only allows 2 concurrent deals."""
        cfg = DCAStrategyConfig.from_preset("BTC/USDT", MarketPreset.CONSERVATIVE)
        engine = DCAEngine(
            symbol=cfg.symbol,
            signal_config=cfg.to_signal_config(),
            order_config=cfg.to_order_config(),
            risk_config=cfg.to_risk_config(),
            trailing_config=cfg.to_trailing_config(),
            false_signal_filter=cfg.to_filter(),
        )

        engine.open_deal(Decimal("3100"))
        engine.open_deal(Decimal("3200"))

        # Third deal should be blocked by risk check
        state = MarketState(
            current_price=Decimal("3000"),
            ema_fast=Decimal("2950"),
            ema_slow=Decimal("3100"),
            adx=30.0,
            rsi=25.0,
            volume_24h=Decimal("2000000"),
            avg_volume=Decimal("1000000"),
            bb_lower=Decimal("2980"),
            nearest_support=Decimal("2950"),
        )
        action = engine.on_price_update(
            state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.should_open_deal is False

    def test_yaml_config_creates_working_engine(self):
        """YAML roundtrip produces config that creates a working engine."""
        original = DCAStrategyConfig.from_preset("ETH/USDT", MarketPreset.AGGRESSIVE)
        yaml_str = original.to_yaml()
        loaded = DCAStrategyConfig.from_yaml(yaml_str)

        engine = DCAEngine(
            symbol=loaded.symbol,
            signal_config=loaded.to_signal_config(),
            order_config=loaded.to_order_config(),
            risk_config=loaded.to_risk_config(),
            trailing_config=loaded.to_trailing_config(),
            false_signal_filter=loaded.to_filter(),
        )
        deal = engine.open_deal(Decimal("2000"))
        assert deal.symbol == "ETH/USDT"


# =========================================================================
# Backtester Tests
# =========================================================================


class TestBacktester:
    @pytest.fixture
    def order_config(self):
        return DCAOrderConfig(
            base_order_volume=Decimal("100"),
            max_safety_orders=3,
            volume_multiplier=Decimal("1.5"),
            price_step_pct=Decimal("2.0"),
            take_profit_pct=Decimal("3.0"),
            stop_loss_pct=Decimal("10.0"),
            max_position_cost=Decimal("5000"),
        )

    def test_backtester_fixed_tp(self, order_config):
        """Fixed TP exits at take profit price."""
        # Price drops then recovers past TP
        prices = [
            Decimal(str(p))
            for p in [
                3100,
                3050,
                3000,
                3050,
                3100,
                3150,
                3200,
                3250,
            ]
        ]
        bt = DCABacktester(
            order_config=order_config,
            trailing_config=TrailingStopConfig(enabled=False),
            label="Fixed TP",
        )
        result = bt.run(prices)
        assert result.total_trades >= 1
        assert result.trades[0].exit_reason == "take_profit"
        assert result.trades[0].profit > 0

    def test_backtester_trailing_stop(self, order_config):
        """Trailing stop captures extended move."""
        # Price rises well past TP level, then drops to trigger trailing
        prices = [
            Decimal(str(p))
            for p in [
                3100,
                3200,
                3300,
                3400,
                3500,
                3600,
                3700,
                3650,  # Drop to trigger trailing (3700*0.992=3674.4)
            ]
        ]
        bt = DCABacktester(
            order_config=order_config,
            trailing_config=TrailingStopConfig(
                enabled=True,
                activation_pct=Decimal("1.5"),
                distance_pct=Decimal("0.8"),
            ),
            label="Trailing Stop",
        )
        result = bt.run(prices)
        assert result.total_trades >= 1
        assert result.trades[0].exit_reason == "trailing_stop"
        assert result.trades[0].profit > 0

    def test_backtester_stop_loss(self, order_config):
        """Stop loss triggers on large drop."""
        # Use no safety orders config for clean SL test
        no_so_config = DCAOrderConfig(
            base_order_volume=Decimal("100"),
            max_safety_orders=0,
            take_profit_pct=Decimal("3.0"),
            stop_loss_pct=Decimal("10.0"),
            max_position_cost=Decimal("5000"),
        )
        prices = [
            Decimal(str(p))
            for p in [
                3100,
                3000,
                2900,
                2780,  # Below SL (3100*0.9=2790)
            ]
        ]
        bt = DCABacktester(
            order_config=no_so_config,
            trailing_config=TrailingStopConfig(enabled=False),
        )
        result = bt.run(prices)
        assert result.total_trades >= 1
        sl_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
        assert len(sl_trades) >= 1

    def test_backtester_safety_orders_fill(self, order_config):
        """Safety orders fill as price drops."""
        prices = [
            Decimal(str(p))
            for p in [
                3100,
                3030,
                2960,
                2890,  # SO1, SO2, SO3 triggers
                3000,
                3100,
                3200,
                3300,  # Recovery past TP
            ]
        ]
        bt = DCABacktester(
            order_config=order_config,
            trailing_config=TrailingStopConfig(enabled=False),
        )
        result = bt.run(prices)
        assert result.total_trades >= 1
        assert result.trades[0].safety_orders_filled > 0

    def test_backtester_multiple_deals(self, order_config):
        """Multiple sequential deals."""
        # Deal 1: opens at 3100, TP at 3100*1.03=3193, exits at 3200
        # Deal 2: opens at 3250 (next price after exit), TP at 3250*1.03=3347.5, exits at 3400
        prices = [
            Decimal(str(p))
            for p in [
                3100,
                3150,
                3200,  # Deal 1 TP at 3200
                3250,
                3300,
                3400,  # Deal 2 TP at 3400
            ]
        ]
        bt = DCABacktester(
            order_config=order_config,
            trailing_config=TrailingStopConfig(enabled=False),
        )
        result = bt.run(prices)
        assert result.total_trades >= 2

    def test_backtest_result_metrics(self, order_config):
        """BacktestResult computes metrics correctly."""
        prices = [
            Decimal(str(p))
            for p in [
                3100,
                3200,
                3300,  # TP
                3100,
                3200,
                3300,  # TP
            ]
        ]
        bt = DCABacktester(
            order_config=order_config,
            trailing_config=TrailingStopConfig(enabled=False),
        )
        result = bt.run(prices)
        assert result.total_trades >= 1
        assert result.winning_trades >= 1
        assert result.win_rate > 0
        assert result.total_profit > 0
        assert result.avg_profit_pct > 0
        assert result.profit_factor > 0

        summary = result.summary()
        assert "total_trades" in summary
        assert "win_rate" in summary
        assert "profit_factor" in summary

    def test_compare_strategies(self, order_config):
        """Compare Fixed TP vs Trailing Stop."""
        # Price rises well above TP then drops
        prices = [
            Decimal(str(p))
            for p in [
                3100,
                3200,
                3300,
                3400,
                3500,
                3600,
                3700,
                3650,  # Trailing stop trigger
            ]
        ]
        results = compare_strategies(
            prices=prices,
            order_config=order_config,
            trailing_config=TrailingStopConfig(
                enabled=True,
                activation_pct=Decimal("1.5"),
                distance_pct=Decimal("0.8"),
            ),
        )
        assert "fixed_tp" in results
        assert "trailing_stop" in results
        assert results["fixed_tp"].total_trades >= 1
        assert results["trailing_stop"].total_trades >= 1

        # On a trending price series, trailing should capture more profit
        fixed_profit = results["fixed_tp"].trades[0].profit_pct
        trailing_profit = results["trailing_stop"].trades[0].profit_pct
        assert trailing_profit > fixed_profit

    def test_empty_price_series(self, order_config):
        """Empty price series returns no trades."""
        bt = DCABacktester(order_config=order_config)
        result = bt.run([])
        assert result.total_trades == 0
        assert result.win_rate == 0
        assert result.profit_factor == 0

    def test_backtest_result_all_wins(self):
        """Profit factor with all winning trades."""
        result = BacktestResult(
            trades=[
                BacktestTrade(
                    entry_price=Decimal("100"),
                    exit_price=Decimal("110"),
                    exit_reason="take_profit",
                    safety_orders_filled=0,
                    profit=Decimal("10"),
                    profit_pct=Decimal("10"),
                    total_cost=Decimal("100"),
                ),
            ]
        )
        assert result.profit_factor == Decimal("999")
        assert result.losing_trades == 0
