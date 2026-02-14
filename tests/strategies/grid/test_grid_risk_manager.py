"""Tests for GridRiskManager v2.0.

Tests position limits, stop-loss, drawdown, trend detection, and comprehensive risk evaluation.
"""

from decimal import Decimal

import pytest

from bot.strategies.grid.grid_risk_manager import (
    GridRiskAction,
    GridRiskConfig,
    GridRiskManager,
    RiskCheckResult,
    TrendState,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def config():
    return GridRiskConfig(
        max_position_size=Decimal("1000"),
        max_total_exposure=Decimal("10000"),
        max_open_orders=20,
        grid_stop_loss_pct=Decimal("0.05"),
        max_unrealized_loss=Decimal("500"),
        max_drawdown_pct=Decimal("0.10"),
        max_consecutive_losses=5,
        trend_atr_multiplier=Decimal("2.0"),
        trend_adx_threshold=25.0,
        min_balance_pct=Decimal("0.20"),
    )


@pytest.fixture
def manager(config):
    return GridRiskManager(config=config)


# =========================================================================
# Config Validation Tests
# =========================================================================


class TestGridRiskConfig:
    def test_defaults(self):
        cfg = GridRiskConfig()
        cfg.validate()  # should not raise

    def test_invalid_position_size(self):
        cfg = GridRiskConfig(max_position_size=Decimal("0"))
        with pytest.raises(ValueError, match="max_position_size must be positive"):
            cfg.validate()

    def test_invalid_exposure(self):
        cfg = GridRiskConfig(max_total_exposure=Decimal("-1"))
        with pytest.raises(ValueError, match="max_total_exposure must be positive"):
            cfg.validate()

    def test_invalid_max_orders(self):
        cfg = GridRiskConfig(max_open_orders=0)
        with pytest.raises(ValueError, match="max_open_orders must be at least 1"):
            cfg.validate()

    def test_invalid_stop_loss(self):
        cfg = GridRiskConfig(grid_stop_loss_pct=Decimal("0"))
        with pytest.raises(ValueError, match="grid_stop_loss_pct must be positive"):
            cfg.validate()

    def test_invalid_drawdown(self):
        cfg = GridRiskConfig(max_drawdown_pct=Decimal("1.5"))
        with pytest.raises(ValueError, match="max_drawdown_pct must be between"):
            cfg.validate()

    def test_invalid_balance_pct(self):
        cfg = GridRiskConfig(min_balance_pct=Decimal("-0.1"))
        with pytest.raises(ValueError, match="min_balance_pct must be between"):
            cfg.validate()


# =========================================================================
# RiskCheckResult Tests
# =========================================================================


class TestRiskCheckResult:
    def test_is_safe_continue(self):
        r = RiskCheckResult(action=GridRiskAction.CONTINUE)
        assert r.is_safe is True

    def test_is_not_safe_pause(self):
        r = RiskCheckResult(action=GridRiskAction.PAUSE)
        assert r.is_safe is False

    def test_to_dict(self):
        r = RiskCheckResult(
            action=GridRiskAction.STOP_LOSS,
            reasons=["price dropped"],
            warnings=["approaching limit"],
        )
        d = r.to_dict()
        assert d["action"] == "stop_loss"
        assert d["is_safe"] is False
        assert len(d["reasons"]) == 1
        assert len(d["warnings"]) == 1


# =========================================================================
# Order Size Validation Tests
# =========================================================================


class TestOrderSizeValidation:
    def test_valid_order(self, manager):
        result = manager.validate_order_size(
            Decimal("500"), Decimal("3000"), 10
        )
        assert result.is_safe
        assert result.action == GridRiskAction.CONTINUE

    def test_order_exceeds_max_size(self, manager):
        result = manager.validate_order_size(
            Decimal("1500"), Decimal("3000"), 10
        )
        assert not result.is_safe
        assert "exceeds max" in result.reasons[0]

    def test_exposure_exceeds_max(self, manager):
        result = manager.validate_order_size(
            Decimal("500"), Decimal("9800"), 10
        )
        assert not result.is_safe
        assert "Total exposure" in result.reasons[0]

    def test_max_open_orders(self, manager):
        result = manager.validate_order_size(
            Decimal("100"), Decimal("1000"), 20
        )
        assert not result.is_safe
        assert "Open orders" in result.reasons[0]

    def test_exposure_warning(self, manager):
        result = manager.validate_order_size(
            Decimal("100"), Decimal("8500"), 10
        )
        assert result.is_safe  # still within limits
        assert len(result.warnings) > 0

    def test_orders_warning(self, manager):
        result = manager.validate_order_size(
            Decimal("100"), Decimal("1000"), 17
        )
        assert result.is_safe
        assert any("Open orders" in w for w in result.warnings)


# =========================================================================
# Stop-Loss Tests
# =========================================================================


class TestGridStopLoss:
    def test_no_stop_loss(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        result = manager.check_grid_stop_loss(Decimal("44500"))
        # 500/45000 ≈ 1.1% < 5%
        assert result.is_safe

    def test_stop_loss_triggered_price_up(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        # 5% above entry
        result = manager.check_grid_stop_loss(Decimal("47300"))
        assert result.action == GridRiskAction.STOP_LOSS

    def test_stop_loss_triggered_price_down(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        # 5% below entry
        result = manager.check_grid_stop_loss(Decimal("42700"))
        assert result.action == GridRiskAction.STOP_LOSS

    def test_stop_loss_unrealized_loss(self, manager):
        result = manager.check_grid_stop_loss(
            Decimal("45000"), unrealized_pnl=Decimal("-600")
        )
        assert result.action == GridRiskAction.STOP_LOSS
        assert "Unrealized loss" in result.reasons[0]

    def test_no_entry_price_set(self, manager):
        result = manager.check_grid_stop_loss(Decimal("45000"))
        assert result.is_safe  # no entry price means no check

    def test_explicit_entry_price(self, manager):
        result = manager.check_grid_stop_loss(
            Decimal("42000"), grid_entry_price=Decimal("45000")
        )
        # 3000/45000 ≈ 6.7% > 5%
        assert result.action == GridRiskAction.STOP_LOSS


# =========================================================================
# Drawdown Tests
# =========================================================================


class TestDrawdown:
    def test_no_drawdown(self, manager):
        result = manager.check_drawdown(Decimal("10000"))
        assert result.is_safe
        assert manager._peak_equity == Decimal("10000")

    def test_equity_increase(self, manager):
        manager.check_drawdown(Decimal("10000"))
        manager.check_drawdown(Decimal("11000"))
        assert manager._peak_equity == Decimal("11000")

    def test_drawdown_within_limit(self, manager):
        manager.check_drawdown(Decimal("10000"))
        result = manager.check_drawdown(Decimal("9500"))
        # 5% drawdown < 10% limit
        assert result.is_safe

    def test_drawdown_exceeded(self, manager):
        manager.check_drawdown(Decimal("10000"))
        result = manager.check_drawdown(Decimal("8900"))
        # 11% drawdown > 10% limit
        assert result.action == GridRiskAction.STOP_LOSS

    def test_drawdown_warning(self, manager):
        manager.check_drawdown(Decimal("10000"))
        result = manager.check_drawdown(Decimal("9250"))
        # 7.5% ≥ 7% (70% of 10%)
        assert result.is_safe
        assert len(result.warnings) > 0


# =========================================================================
# Consecutive Loss Tests
# =========================================================================


class TestConsecutiveLosses:
    def test_no_losses(self, manager):
        result = manager.check_consecutive_losses()
        assert result.is_safe

    def test_losses_under_limit(self, manager):
        for _ in range(4):
            manager.record_trade_result(Decimal("-10"))
        result = manager.check_consecutive_losses()
        assert result.is_safe
        assert manager._consecutive_losses == 4

    def test_losses_at_limit(self, manager):
        for _ in range(5):
            manager.record_trade_result(Decimal("-10"))
        result = manager.check_consecutive_losses()
        assert result.action == GridRiskAction.PAUSE

    def test_win_resets_counter(self, manager):
        for _ in range(3):
            manager.record_trade_result(Decimal("-10"))
        manager.record_trade_result(Decimal("20"))  # win resets
        assert manager._consecutive_losses == 0

    def test_pnl_tracking(self, manager):
        manager.record_trade_result(Decimal("100"))
        manager.record_trade_result(Decimal("-30"))
        assert manager._total_realized_pnl == Decimal("70")


# =========================================================================
# Trend Detection Tests
# =========================================================================


class TestTrendDetection:
    def test_ranging_market(self, manager):
        result = manager.check_trend_suitability(
            atr=Decimal("500"), price_move=Decimal("300")
        )
        assert result.is_safe

    def test_strong_trend_atr(self, manager):
        result = manager.check_trend_suitability(
            atr=Decimal("500"), price_move=Decimal("1200")
        )
        assert result.action == GridRiskAction.DEACTIVATE

    def test_strong_trend_adx(self, manager):
        result = manager.check_trend_suitability(
            atr=Decimal("500"), price_move=Decimal("300"), adx=30.0
        )
        assert result.action == GridRiskAction.DEACTIVATE

    def test_both_atr_and_adx_trending(self, manager):
        result = manager.check_trend_suitability(
            atr=Decimal("500"), price_move=Decimal("1200"), adx=35.0
        )
        assert result.action == GridRiskAction.DEACTIVATE
        assert len(result.reasons) == 2  # both triggers

    def test_mild_trend_warning(self, manager):
        # 70% of threshold: 500*2*0.7 = 700
        result = manager.check_trend_suitability(
            atr=Decimal("500"), price_move=Decimal("750")
        )
        assert result.is_safe
        assert len(result.warnings) > 0

    def test_classify_ranging(self, manager):
        state = manager.classify_trend(
            atr=Decimal("500"), price_move=Decimal("300")
        )
        assert state == TrendState.RANGING

    def test_classify_mild_trend(self, manager):
        state = manager.classify_trend(
            atr=Decimal("500"), price_move=Decimal("750")
        )
        assert state == TrendState.MILD_TREND

    def test_classify_strong_trend(self, manager):
        state = manager.classify_trend(
            atr=Decimal("500"), price_move=Decimal("1200")
        )
        assert state == TrendState.STRONG_TREND

    def test_classify_strong_trend_adx(self, manager):
        state = manager.classify_trend(
            atr=Decimal("500"), price_move=Decimal("300"), adx=30.0
        )
        assert state == TrendState.STRONG_TREND

    def test_classify_zero_atr(self, manager):
        state = manager.classify_trend(
            atr=Decimal("0"), price_move=Decimal("300")
        )
        assert state == TrendState.RANGING


# =========================================================================
# Balance Protection Tests
# =========================================================================


class TestBalanceProtection:
    def test_sufficient_balance(self, manager):
        result = manager.check_balance(Decimal("3000"), Decimal("10000"))
        assert result.is_safe

    def test_insufficient_free_balance(self, manager):
        result = manager.check_balance(Decimal("1500"), Decimal("10000"))
        # 15% < 20%
        assert result.action == GridRiskAction.PAUSE

    def test_zero_balance(self, manager):
        result = manager.check_balance(Decimal("0"), Decimal("0"))
        assert result.action == GridRiskAction.PAUSE

    def test_exact_threshold(self, manager):
        result = manager.check_balance(Decimal("2000"), Decimal("10000"))
        # 20% == 20% — not below
        assert result.is_safe


# =========================================================================
# Comprehensive Risk Evaluation Tests
# =========================================================================


class TestEvaluateRisk:
    def test_all_clear(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        result = manager.evaluate_risk(
            current_price=Decimal("45000"),
            current_equity=Decimal("10000"),
            current_exposure=Decimal("5000"),
            open_orders=10,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert result.is_safe

    def test_stop_loss_priority(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        result = manager.evaluate_risk(
            current_price=Decimal("42000"),  # >5% drop → stop loss
            current_equity=Decimal("10000"),
            current_exposure=Decimal("5000"),
            open_orders=10,
        )
        assert result.action == GridRiskAction.STOP_LOSS

    def test_deactivate_on_trend(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        result = manager.evaluate_risk(
            current_price=Decimal("45000"),
            current_equity=Decimal("10000"),
            current_exposure=Decimal("5000"),
            open_orders=10,
            atr=Decimal("500"),
            price_move=Decimal("1200"),
        )
        assert result.action == GridRiskAction.DEACTIVATE

    def test_stop_loss_overrides_deactivate(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        result = manager.evaluate_risk(
            current_price=Decimal("42000"),  # stop loss trigger
            current_equity=Decimal("10000"),
            current_exposure=Decimal("5000"),
            open_orders=10,
            atr=Decimal("500"),
            price_move=Decimal("1200"),  # also trending
        )
        # Stop loss has higher priority than deactivate
        assert result.action == GridRiskAction.STOP_LOSS

    def test_multiple_warnings_merged(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        manager.check_drawdown(Decimal("10000"))  # set peak
        result = manager.evaluate_risk(
            current_price=Decimal("45000"),
            current_equity=Decimal("9300"),  # 7% DD → warning
            current_exposure=Decimal("5000"),
            open_orders=10,
            atr=Decimal("500"),
            price_move=Decimal("750"),  # mild trend → warning
        )
        assert result.is_safe
        assert len(result.warnings) > 0


# =========================================================================
# State Management Tests
# =========================================================================


class TestStateManagement:
    def test_set_grid_entry_price(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        assert manager._grid_entry_price == Decimal("45000")

    def test_reset(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        manager.check_drawdown(Decimal("10000"))
        manager.record_trade_result(Decimal("-50"))
        manager.reset()
        assert manager._peak_equity == Decimal("0")
        assert manager._consecutive_losses == 0
        assert manager._grid_entry_price == Decimal("0")
        assert manager._total_realized_pnl == Decimal("0")

    def test_statistics(self, manager):
        manager.set_grid_entry_price(Decimal("45000"))
        stats = manager.get_statistics()
        assert stats["grid_entry_price"] == "45000"
        assert stats["config"]["max_position_size"] == "1000"
        assert stats["config"]["max_open_orders"] == 20

    def test_default_config(self):
        mgr = GridRiskManager()
        assert mgr.config.max_position_size == Decimal("1000")
