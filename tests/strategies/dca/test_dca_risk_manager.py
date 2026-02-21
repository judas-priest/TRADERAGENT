"""Tests for DCA Risk Manager v2.0.

Tests drawdown limits, capital allocation, emergency stop-loss,
concurrent position limits, daily loss, and pump & dump protection.
"""

from decimal import Decimal

import pytest

from bot.strategies.dca.dca_risk_manager import (
    DCARiskAction,
    DCARiskConfig,
    DCARiskManager,
    DealRiskState,
    PortfolioRiskState,
    RiskCheckResult,
)

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def config():
    return DCARiskConfig(
        max_concurrent_deals=3,
        max_position_cost=Decimal("5000"),
        max_total_exposure=Decimal("15000"),
        deal_stop_loss_pct=Decimal("10.0"),
        max_deal_drawdown_pct=Decimal("15.0"),
        max_portfolio_drawdown_pct=Decimal("10.0"),
        max_daily_loss=Decimal("500"),
        max_consecutive_losses=5,
        min_balance_pct=Decimal("0.20"),
        max_price_change_pct=Decimal("10.0"),
    )


@pytest.fixture
def manager(config):
    return DCARiskManager(config)


@pytest.fixture
def safe_deal():
    return DealRiskState(
        deal_id="DCA-0001",
        symbol="BTC/USDT",
        entry_price=Decimal("3100"),
        average_entry_price=Decimal("3050"),
        current_price=Decimal("3000"),
        total_cost=Decimal("1000"),
        total_volume=Decimal("0.33"),
        safety_orders_filled=1,
        max_safety_orders=5,
        unrealized_pnl=Decimal("-50"),
        unrealized_pnl_pct=Decimal("-5.0"),
    )


@pytest.fixture
def safe_portfolio(safe_deal):
    return PortfolioRiskState(
        active_deals=[safe_deal],
        total_equity=Decimal("10000"),
        available_balance=Decimal("5000"),
        total_balance=Decimal("10000"),
        daily_realized_pnl=Decimal("-100"),
    )


# =========================================================================
# Config Validation Tests
# =========================================================================


class TestDCARiskConfig:
    def test_defaults(self):
        cfg = DCARiskConfig()
        cfg.validate()

    def test_invalid_concurrent_deals(self):
        cfg = DCARiskConfig(max_concurrent_deals=0)
        with pytest.raises(ValueError, match="max_concurrent_deals"):
            cfg.validate()

    def test_invalid_position_cost(self):
        cfg = DCARiskConfig(max_position_cost=Decimal("0"))
        with pytest.raises(ValueError, match="max_position_cost"):
            cfg.validate()

    def test_invalid_total_exposure(self):
        cfg = DCARiskConfig(max_total_exposure=Decimal("-1"))
        with pytest.raises(ValueError, match="max_total_exposure"):
            cfg.validate()

    def test_invalid_stop_loss(self):
        cfg = DCARiskConfig(deal_stop_loss_pct=Decimal("0"))
        with pytest.raises(ValueError, match="deal_stop_loss_pct"):
            cfg.validate()

    def test_invalid_deal_drawdown(self):
        cfg = DCARiskConfig(max_deal_drawdown_pct=Decimal("101"))
        with pytest.raises(ValueError, match="max_deal_drawdown_pct"):
            cfg.validate()

    def test_invalid_portfolio_drawdown(self):
        cfg = DCARiskConfig(max_portfolio_drawdown_pct=Decimal("0"))
        with pytest.raises(ValueError, match="max_portfolio_drawdown_pct"):
            cfg.validate()

    def test_invalid_daily_loss(self):
        cfg = DCARiskConfig(max_daily_loss=Decimal("-1"))
        with pytest.raises(ValueError, match="max_daily_loss"):
            cfg.validate()

    def test_invalid_consecutive_losses(self):
        cfg = DCARiskConfig(max_consecutive_losses=0)
        with pytest.raises(ValueError, match="max_consecutive_losses"):
            cfg.validate()

    def test_invalid_balance_pct(self):
        cfg = DCARiskConfig(min_balance_pct=Decimal("1.5"))
        with pytest.raises(ValueError, match="min_balance_pct"):
            cfg.validate()

    def test_invalid_price_change(self):
        cfg = DCARiskConfig(max_price_change_pct=Decimal("0"))
        with pytest.raises(ValueError, match="max_price_change_pct"):
            cfg.validate()


# =========================================================================
# RiskCheckResult Tests
# =========================================================================


class TestRiskCheckResult:
    def test_continue_is_safe(self):
        r = RiskCheckResult()
        assert r.is_safe is True

    def test_pause_is_not_safe(self):
        r = RiskCheckResult(action=DCARiskAction.PAUSE)
        assert r.is_safe is False

    def test_to_dict(self):
        r = RiskCheckResult(
            action=DCARiskAction.CLOSE_DEAL,
            reasons=["stop loss"],
            warnings=["warning"],
        )
        d = r.to_dict()
        assert d["action"] == "close_deal"
        assert d["is_safe"] is False
        assert len(d["reasons"]) == 1


# =========================================================================
# Deal Stop Loss Tests
# =========================================================================


class TestDealStopLoss:
    def test_no_stop_loss(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("3000"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
        )
        result = manager.check_deal_stop_loss(deal)
        assert result.is_safe  # ~3.2% < 10%

    def test_stop_loss_triggered(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("2750"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
        )
        result = manager.check_deal_stop_loss(deal)
        assert result.action == DCARiskAction.CLOSE_DEAL
        # 350/3100 = 11.3% > 10%

    def test_stop_loss_warning(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("2880"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
        )
        result = manager.check_deal_stop_loss(deal)
        assert result.is_safe
        assert len(result.warnings) > 0  # ~7.1% >= 7% (70% of 10%)

    def test_stop_loss_from_average(self):
        cfg = DCARiskConfig(deal_stop_loss_from_average=True, deal_stop_loss_pct=Decimal("10.0"))
        mgr = DCARiskManager(cfg)
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3000"),
            current_price=Decimal("2680"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.33"),
            safety_orders_filled=1,
            max_safety_orders=5,
        )
        result = mgr.check_deal_stop_loss(deal)
        # (3000-2680)/3000 = 10.7% > 10% — triggered
        assert result.action == DCARiskAction.CLOSE_DEAL


# =========================================================================
# Deal Drawdown Tests
# =========================================================================


class TestDealDrawdown:
    def test_no_drawdown(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("3200"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
            unrealized_pnl=Decimal("32"),
            unrealized_pnl_pct=Decimal("3.2"),
        )
        result = manager.check_deal_drawdown(deal)
        assert result.is_safe

    def test_drawdown_exceeded(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("2600"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
            unrealized_pnl=Decimal("-160"),
            unrealized_pnl_pct=Decimal("-16.0"),
        )
        result = manager.check_deal_drawdown(deal)
        assert result.action == DCARiskAction.CLOSE_DEAL

    def test_drawdown_warning(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("2750"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
            unrealized_pnl=Decimal("-112"),
            unrealized_pnl_pct=Decimal("-11.2"),
        )
        result = manager.check_deal_drawdown(deal)
        assert result.is_safe
        assert len(result.warnings) > 0  # 11.2% >= 10.5% (70% of 15%)


# =========================================================================
# Concurrent Deals Tests
# =========================================================================


class TestConcurrentDeals:
    def test_within_limit(self, manager):
        result = manager.check_concurrent_deals(1)
        assert result.is_safe

    def test_at_limit(self, manager):
        result = manager.check_concurrent_deals(3)
        assert result.action == DCARiskAction.PAUSE

    def test_over_limit(self, manager):
        result = manager.check_concurrent_deals(5)
        assert result.action == DCARiskAction.PAUSE

    def test_approaching_limit(self, manager):
        result = manager.check_concurrent_deals(2)
        assert result.is_safe
        assert len(result.warnings) > 0


# =========================================================================
# Portfolio Drawdown Tests
# =========================================================================


class TestPortfolioDrawdown:
    def test_no_drawdown(self, manager):
        result = manager.check_portfolio_drawdown(Decimal("10000"))
        assert result.is_safe
        assert manager._peak_equity == Decimal("10000")

    def test_new_peak(self, manager):
        manager.check_portfolio_drawdown(Decimal("10000"))
        manager.check_portfolio_drawdown(Decimal("11000"))
        assert manager._peak_equity == Decimal("11000")

    def test_drawdown_exceeded(self, manager):
        manager.check_portfolio_drawdown(Decimal("10000"))
        result = manager.check_portfolio_drawdown(Decimal("8900"))
        # 11% > 10%
        assert result.action == DCARiskAction.CLOSE_ALL

    def test_drawdown_warning(self, manager):
        manager.check_portfolio_drawdown(Decimal("10000"))
        result = manager.check_portfolio_drawdown(Decimal("9250"))
        # 7.5% >= 7% (70% of 10%)
        assert result.is_safe
        assert len(result.warnings) > 0

    def test_zero_peak(self, manager):
        result = manager.check_portfolio_drawdown(Decimal("0"))
        assert result.is_safe


# =========================================================================
# Daily Loss Tests
# =========================================================================


class TestDailyLoss:
    def test_within_limit(self, manager):
        result = manager.check_daily_loss(Decimal("-300"))
        assert result.is_safe

    def test_exceeded(self, manager):
        result = manager.check_daily_loss(Decimal("-600"))
        assert result.action == DCARiskAction.PAUSE

    def test_warning(self, manager):
        result = manager.check_daily_loss(Decimal("-380"))
        assert result.is_safe
        assert len(result.warnings) > 0  # -380 < -350 (70% of 500)

    def test_uses_internal_tracking(self, manager):
        manager.record_trade_result(Decimal("-300"))
        manager.record_trade_result(Decimal("-250"))
        result = manager.check_daily_loss()
        assert result.action == DCARiskAction.PAUSE


# =========================================================================
# Consecutive Loss Tests
# =========================================================================


class TestConsecutiveLosses:
    def test_no_losses(self, manager):
        result = manager.check_consecutive_losses()
        assert result.is_safe

    def test_under_limit(self, manager):
        for _ in range(4):
            manager.record_trade_result(Decimal("-10"))
        result = manager.check_consecutive_losses()
        assert result.is_safe

    def test_at_limit(self, manager):
        for _ in range(5):
            manager.record_trade_result(Decimal("-10"))
        result = manager.check_consecutive_losses()
        assert result.action == DCARiskAction.PAUSE

    def test_win_resets(self, manager):
        for _ in range(3):
            manager.record_trade_result(Decimal("-10"))
        manager.record_trade_result(Decimal("50"))
        assert manager._consecutive_losses == 0


# =========================================================================
# Balance Protection Tests
# =========================================================================


class TestBalanceProtection:
    def test_sufficient(self, manager):
        result = manager.check_balance(Decimal("3000"), Decimal("10000"))
        assert result.is_safe

    def test_insufficient(self, manager):
        result = manager.check_balance(Decimal("1500"), Decimal("10000"))
        assert result.action == DCARiskAction.PAUSE

    def test_zero_balance(self, manager):
        result = manager.check_balance(Decimal("0"), Decimal("0"))
        assert result.action == DCARiskAction.PAUSE


# =========================================================================
# Total Exposure Tests
# =========================================================================


class TestTotalExposure:
    def test_within_limit(self, manager, safe_deal):
        result = manager.check_total_exposure([safe_deal])
        assert result.is_safe

    def test_exceeded(self, manager):
        deals = [
            DealRiskState(
                deal_id=f"D{i}",
                symbol="BTC",
                entry_price=Decimal("3100"),
                average_entry_price=Decimal("3100"),
                current_price=Decimal("3000"),
                total_cost=Decimal("6000"),
                total_volume=Decimal("2.0"),
                safety_orders_filled=0,
                max_safety_orders=5,
            )
            for i in range(3)
        ]
        result = manager.check_total_exposure(deals)
        # 6000 * 3 = 18000 > 15000
        assert result.action == DCARiskAction.PAUSE

    def test_warning(self, manager):
        deals = [
            DealRiskState(
                deal_id="D1",
                symbol="BTC",
                entry_price=Decimal("3100"),
                average_entry_price=Decimal("3100"),
                current_price=Decimal("3000"),
                total_cost=Decimal("13000"),
                total_volume=Decimal("4.0"),
                safety_orders_filled=0,
                max_safety_orders=5,
            )
        ]
        result = manager.check_total_exposure(deals)
        # 13000 > 12750 (85% of 15000)
        assert result.is_safe
        assert len(result.warnings) > 0


# =========================================================================
# Price Change (Pump & Dump) Tests
# =========================================================================


class TestPriceChange:
    def test_normal_change(self, manager):
        result = manager.check_price_change(Decimal("3100"), Decimal("3200"))
        assert result.is_safe

    def test_extreme_increase(self, manager):
        result = manager.check_price_change(Decimal("3100"), Decimal("3500"))
        # 12.9% > 10%
        assert result.action == DCARiskAction.PAUSE

    def test_extreme_decrease(self, manager):
        result = manager.check_price_change(Decimal("3100"), Decimal("2700"))
        # 12.9% > 10%
        assert result.action == DCARiskAction.PAUSE

    def test_no_pause_on_volatility_disabled(self):
        cfg = DCARiskConfig(pause_on_extreme_volatility=False)
        mgr = DCARiskManager(cfg)
        result = mgr.check_price_change(Decimal("3100"), Decimal("3500"))
        assert result.is_safe  # Warning only
        assert len(result.warnings) > 0

    def test_zero_previous_price(self, manager):
        result = manager.check_price_change(Decimal("0"), Decimal("3100"))
        assert result.is_safe


# =========================================================================
# Can Open New Deal Tests
# =========================================================================


class TestCanOpenNewDeal:
    def test_can_open(self, manager):
        result = manager.can_open_new_deal(
            active_deal_count=1,
            deal_cost=Decimal("1000"),
            current_exposure=Decimal("5000"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert result.is_safe

    def test_blocked_by_deals(self, manager):
        result = manager.can_open_new_deal(
            active_deal_count=3,
            deal_cost=Decimal("1000"),
            current_exposure=Decimal("5000"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert not result.is_safe
        assert "concurrent" in result.reasons[0].lower()

    def test_blocked_by_exposure(self, manager):
        result = manager.can_open_new_deal(
            active_deal_count=1,
            deal_cost=Decimal("1000"),
            current_exposure=Decimal("14500"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert not result.is_safe
        assert "exposure" in result.reasons[0].lower()

    def test_blocked_by_deal_cost(self, manager):
        result = manager.can_open_new_deal(
            active_deal_count=1,
            deal_cost=Decimal("6000"),
            current_exposure=Decimal("5000"),
            available_balance=Decimal("7000"),
            total_balance=Decimal("10000"),
        )
        assert not result.is_safe
        assert "cost exceeds" in result.reasons[0].lower()

    def test_blocked_by_balance(self, manager):
        result = manager.can_open_new_deal(
            active_deal_count=1,
            deal_cost=Decimal("4500"),
            current_exposure=Decimal("5000"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert not result.is_safe
        assert "balance" in result.reasons[0].lower()

    def test_blocked_by_daily_loss(self, manager):
        for _ in range(3):
            manager.record_trade_result(Decimal("-200"))
        result = manager.can_open_new_deal(
            active_deal_count=0,
            deal_cost=Decimal("100"),
            current_exposure=Decimal("0"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert not result.is_safe

    def test_blocked_by_consecutive_losses(self, manager):
        for _ in range(5):
            manager.record_trade_result(Decimal("-10"))
        result = manager.can_open_new_deal(
            active_deal_count=0,
            deal_cost=Decimal("100"),
            current_exposure=Decimal("0"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert not result.is_safe


# =========================================================================
# Full Risk Evaluation Tests
# =========================================================================


class TestEvaluateRisk:
    def test_all_safe(self, manager, safe_portfolio):
        manager.check_portfolio_drawdown(Decimal("10000"))  # set peak
        result = manager.evaluate_risk(safe_portfolio)
        assert result.is_safe

    def test_deal_stop_loss_triggers(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("2700"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
            unrealized_pnl=Decimal("-128"),
            unrealized_pnl_pct=Decimal("-12.9"),
        )
        state = PortfolioRiskState(
            active_deals=[deal],
            total_equity=Decimal("10000"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        manager.check_portfolio_drawdown(Decimal("10000"))
        result = manager.evaluate_risk(state)
        assert result.action == DCARiskAction.CLOSE_DEAL

    def test_portfolio_drawdown_overrides(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("3000"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
        )
        state = PortfolioRiskState(
            active_deals=[deal],
            total_equity=Decimal("8800"),  # 12% drop from peak 10000
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        manager.check_portfolio_drawdown(Decimal("10000"))
        result = manager.evaluate_risk(state)
        assert result.action == DCARiskAction.CLOSE_ALL

    def test_warnings_collected(self, manager):
        deal = DealRiskState(
            deal_id="D1",
            symbol="BTC",
            entry_price=Decimal("3100"),
            average_entry_price=Decimal("3100"),
            current_price=Decimal("2880"),
            total_cost=Decimal("1000"),
            total_volume=Decimal("0.32"),
            safety_orders_filled=0,
            max_safety_orders=5,
            unrealized_pnl=Decimal("-70"),
            unrealized_pnl_pct=Decimal("-7.1"),
        )
        state = PortfolioRiskState(
            active_deals=[deal],
            total_equity=Decimal("10000"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        manager.check_portfolio_drawdown(Decimal("10000"))
        result = manager.evaluate_risk(state)
        assert result.is_safe
        # Should have deal SL warning (~7.1% >= 7% threshold)
        assert len(result.warnings) > 0


# =========================================================================
# State Management Tests
# =========================================================================


class TestStateManagement:
    def test_record_trade_result(self, manager):
        manager.record_trade_result(Decimal("100"))
        assert manager._total_realized_pnl == Decimal("100")
        assert manager._consecutive_losses == 0

    def test_record_loss(self, manager):
        manager.record_trade_result(Decimal("-50"))
        assert manager._consecutive_losses == 1
        assert manager._daily_realized_pnl == Decimal("-50")

    def test_reset_daily_pnl(self, manager):
        manager.record_trade_result(Decimal("-200"))
        manager.reset_daily_pnl()
        assert manager._daily_realized_pnl == Decimal("0")
        assert manager._total_realized_pnl == Decimal("-200")  # Total unchanged

    def test_full_reset(self, manager):
        manager.record_trade_result(Decimal("-200"))
        manager.check_portfolio_drawdown(Decimal("10000"))
        manager.reset()
        assert manager._peak_equity == Decimal("0")
        assert manager._consecutive_losses == 0
        assert manager._total_realized_pnl == Decimal("0")
        assert manager._daily_realized_pnl == Decimal("0")

    def test_statistics(self, manager):
        manager.record_trade_result(Decimal("-50"))
        stats = manager.get_statistics()
        assert stats["consecutive_losses"] == 1
        assert stats["total_realized_pnl"] == "-50"
        assert stats["config"]["max_concurrent_deals"] == 3

    def test_default_manager(self):
        mgr = DCARiskManager()
        assert mgr.config.max_concurrent_deals == 3
