"""Tests for GridRiskManager."""

from decimal import Decimal

import pytest

from grid_backtester.core.risk_manager import (
    GridRiskAction,
    GridRiskConfig,
    GridRiskManager,
    RiskCheckResult,
    TrendState,
)


class TestGridRiskConfig:

    def test_default_config(self):
        config = GridRiskConfig()
        config.validate()

    def test_invalid_position_size(self):
        config = GridRiskConfig(max_position_size=Decimal("-1"))
        with pytest.raises(ValueError):
            config.validate()

    def test_invalid_drawdown(self):
        config = GridRiskConfig(max_drawdown_pct=Decimal("1.5"))
        with pytest.raises(ValueError):
            config.validate()


class TestOrderValidation:

    def test_valid_order(self):
        mgr = GridRiskManager()
        result = mgr.validate_order_size(
            order_quote_value=Decimal("100"),
            current_total_exposure=Decimal("500"),
            current_open_orders=5,
        )
        assert result.is_safe

    def test_exceeds_position_size(self):
        mgr = GridRiskManager()
        result = mgr.validate_order_size(
            order_quote_value=Decimal("2000"),
            current_total_exposure=Decimal("500"),
            current_open_orders=5,
        )
        assert result.action == GridRiskAction.PAUSE
        assert len(result.reasons) > 0

    def test_exceeds_total_exposure(self):
        mgr = GridRiskManager()
        result = mgr.validate_order_size(
            order_quote_value=Decimal("100"),
            current_total_exposure=Decimal("9950"),
            current_open_orders=5,
        )
        assert result.action == GridRiskAction.PAUSE

    def test_exceeds_max_orders(self):
        mgr = GridRiskManager()
        result = mgr.validate_order_size(
            order_quote_value=Decimal("100"),
            current_total_exposure=Decimal("500"),
            current_open_orders=50,
        )
        assert result.action == GridRiskAction.PAUSE


class TestStopLoss:

    def test_no_stop_loss(self):
        mgr = GridRiskManager()
        result = mgr.check_grid_stop_loss(
            current_price=Decimal("45000"),
            grid_entry_price=Decimal("45100"),
        )
        assert result.is_safe

    def test_stop_loss_triggered(self):
        mgr = GridRiskManager()
        result = mgr.check_grid_stop_loss(
            current_price=Decimal("42000"),
            grid_entry_price=Decimal("45000"),
        )
        assert result.action == GridRiskAction.STOP_LOSS

    def test_unrealized_loss_stop(self):
        mgr = GridRiskManager()
        result = mgr.check_grid_stop_loss(
            current_price=Decimal("45000"),
            grid_entry_price=Decimal("45000"),
            unrealized_pnl=Decimal("-600"),
        )
        assert result.action == GridRiskAction.STOP_LOSS


class TestDrawdown:

    def test_no_drawdown(self):
        mgr = GridRiskManager()
        mgr.check_drawdown(Decimal("10000"))
        result = mgr.check_drawdown(Decimal("10000"))
        assert result.is_safe

    def test_drawdown_triggered(self):
        mgr = GridRiskManager()
        mgr.check_drawdown(Decimal("10000"))
        result = mgr.check_drawdown(Decimal("8900"))
        assert result.action == GridRiskAction.STOP_LOSS

    def test_drawdown_warning(self):
        mgr = GridRiskManager()
        mgr.check_drawdown(Decimal("10000"))
        result = mgr.check_drawdown(Decimal("9250"))
        assert result.is_safe
        assert len(result.warnings) > 0


class TestConsecutiveLosses:

    def test_below_limit(self):
        mgr = GridRiskManager()
        for _ in range(3):
            mgr.record_trade_result(Decimal("-10"))
        result = mgr.check_consecutive_losses()
        assert result.is_safe

    def test_at_limit(self):
        mgr = GridRiskManager()
        for _ in range(5):
            mgr.record_trade_result(Decimal("-10"))
        result = mgr.check_consecutive_losses()
        assert result.action == GridRiskAction.PAUSE

    def test_reset_on_profit(self):
        mgr = GridRiskManager()
        for _ in range(4):
            mgr.record_trade_result(Decimal("-10"))
        mgr.record_trade_result(Decimal("10"))
        result = mgr.check_consecutive_losses()
        assert result.is_safe


class TestTrendSuitability:

    def test_ranging_market(self):
        mgr = GridRiskManager()
        result = mgr.check_trend_suitability(
            atr=Decimal("100"),
            price_move=Decimal("50"),
        )
        assert result.is_safe

    def test_strong_trend(self):
        mgr = GridRiskManager()
        result = mgr.check_trend_suitability(
            atr=Decimal("100"),
            price_move=Decimal("250"),
        )
        assert result.action == GridRiskAction.DEACTIVATE

    def test_adx_trend(self):
        mgr = GridRiskManager()
        result = mgr.check_trend_suitability(
            atr=Decimal("100"),
            price_move=Decimal("50"),
            adx=30.0,
        )
        assert result.action == GridRiskAction.DEACTIVATE


class TestClassifyTrend:

    def test_ranging(self):
        mgr = GridRiskManager()
        state = mgr.classify_trend(Decimal("100"), Decimal("50"))
        assert state == TrendState.RANGING

    def test_strong(self):
        mgr = GridRiskManager()
        state = mgr.classify_trend(Decimal("100"), Decimal("250"))
        assert state == TrendState.STRONG_TREND

    def test_mild(self):
        mgr = GridRiskManager()
        state = mgr.classify_trend(Decimal("100"), Decimal("150"))
        assert state == TrendState.MILD_TREND

    def test_zero_atr(self):
        mgr = GridRiskManager()
        state = mgr.classify_trend(Decimal("0"), Decimal("100"))
        assert state == TrendState.RANGING


class TestBalanceCheck:

    def test_sufficient(self):
        mgr = GridRiskManager()
        result = mgr.check_balance(Decimal("3000"), Decimal("10000"))
        assert result.is_safe

    def test_insufficient(self):
        mgr = GridRiskManager()
        result = mgr.check_balance(Decimal("1000"), Decimal("10000"))
        assert result.action == GridRiskAction.PAUSE

    def test_zero_balance(self):
        mgr = GridRiskManager()
        result = mgr.check_balance(Decimal("0"), Decimal("0"))
        assert result.action == GridRiskAction.PAUSE


class TestEvaluateRisk:

    def test_all_safe(self):
        mgr = GridRiskManager()
        mgr.set_grid_entry_price(Decimal("45000"))
        result = mgr.evaluate_risk(
            current_price=Decimal("45100"),
            current_equity=Decimal("10000"),
            current_exposure=Decimal("5000"),
            open_orders=10,
        )
        assert result.is_safe

    def test_stop_loss_priority(self):
        mgr = GridRiskManager()
        mgr.set_grid_entry_price(Decimal("45000"))
        result = mgr.evaluate_risk(
            current_price=Decimal("40000"),
            current_equity=Decimal("10000"),
            current_exposure=Decimal("5000"),
            open_orders=10,
        )
        assert result.action == GridRiskAction.STOP_LOSS


class TestResetAndStats:

    def test_reset(self):
        mgr = GridRiskManager()
        mgr.set_grid_entry_price(Decimal("45000"))
        mgr.record_trade_result(Decimal("-10"))
        mgr.check_drawdown(Decimal("10000"))
        mgr.reset()

        stats = mgr.get_statistics()
        assert stats["consecutive_losses"] == 0
        assert stats["grid_entry_price"] == "0"

    def test_statistics_keys(self):
        mgr = GridRiskManager()
        stats = mgr.get_statistics()
        assert "peak_equity" in stats
        assert "config" in stats
        assert "max_position_size" in stats["config"]

    def test_result_to_dict(self):
        result = RiskCheckResult(
            action=GridRiskAction.PAUSE,
            reasons=["test reason"],
            warnings=["test warning"],
        )
        d = result.to_dict()
        assert d["action"] == "pause"
        assert not d["is_safe"]
        assert "test reason" in d["reasons"]
