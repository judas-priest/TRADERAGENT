"""
Tests for TrendFollowerConfig — configuration dataclass.
"""

from decimal import Decimal

from bot.strategies.trend_follower.config import (
    DEFAULT_TREND_FOLLOWER_CONFIG,
    TrendFollowerConfig,
)


class TestTrendFollowerConfig:
    def test_default_instance(self):
        cfg = DEFAULT_TREND_FOLLOWER_CONFIG
        assert isinstance(cfg, TrendFollowerConfig)

    def test_ema_periods(self):
        cfg = TrendFollowerConfig()
        assert cfg.ema_fast_period == 20
        assert cfg.ema_slow_period == 50

    def test_atr_rsi_periods(self):
        cfg = TrendFollowerConfig()
        assert cfg.atr_period == 14
        assert cfg.rsi_period == 14

    def test_rsi_thresholds(self):
        cfg = TrendFollowerConfig()
        assert cfg.rsi_oversold == Decimal("30")
        assert cfg.rsi_overbought == Decimal("70")

    def test_risk_params(self):
        cfg = TrendFollowerConfig()
        assert cfg.risk_per_trade_pct == Decimal("0.01")
        assert cfg.max_risk_per_trade_pct == Decimal("0.01")
        assert cfg.max_total_exposure_pct == Decimal("0.20")

    def test_position_limits(self):
        cfg = TrendFollowerConfig()
        assert cfg.max_positions == 20
        assert cfg.max_position_size_usd == Decimal("10000")

    def test_drawdown_protection(self):
        cfg = TrendFollowerConfig()
        assert cfg.max_consecutive_losses == 3
        assert cfg.size_reduction_factor == Decimal("0.5")

    def test_trailing_stop(self):
        cfg = TrendFollowerConfig()
        assert cfg.enable_trailing_stop is True
        assert cfg.trailing_activation_atr == Decimal("1.5")
        assert cfg.trailing_distance_atr == Decimal("0.5")

    def test_breakeven(self):
        cfg = TrendFollowerConfig()
        assert cfg.enable_breakeven is True
        assert cfg.breakeven_activation_atr == Decimal("1.0")

    def test_partial_close(self):
        cfg = TrendFollowerConfig()
        assert cfg.enable_partial_close is True
        assert cfg.partial_close_percentage == Decimal("0.50")
        assert cfg.partial_tp_percentage == Decimal("0.70")

    def test_tp_sl_multipliers(self):
        cfg = TrendFollowerConfig()
        assert len(cfg.tp_multipliers) == 3
        assert len(cfg.sl_multipliers) == 3

    def test_custom_override(self):
        cfg = TrendFollowerConfig(
            ema_fast_period=10,
            risk_per_trade_pct=Decimal("0.02"),
            max_positions=10,
        )
        assert cfg.ema_fast_period == 10
        assert cfg.risk_per_trade_pct == Decimal("0.02")
        assert cfg.max_positions == 10

    def test_volume_params(self):
        cfg = TrendFollowerConfig()
        assert cfg.require_volume_confirmation is True
        assert cfg.volume_multiplier == Decimal("1.5")
        assert cfg.volume_lookback == 20

    def test_performance_targets(self):
        cfg = TrendFollowerConfig()
        assert cfg.min_sharpe_ratio == Decimal("1.0")
        assert cfg.max_drawdown_pct == Decimal("0.20")
        assert cfg.min_profit_factor == Decimal("1.5")
        assert cfg.min_win_rate_pct == Decimal("45")

    def test_exchange_params(self):
        cfg = TrendFollowerConfig()
        assert cfg.use_limit_orders is True
        assert cfg.max_slippage_pct == Decimal("0.005")
        assert cfg.order_timeout_seconds == 60
