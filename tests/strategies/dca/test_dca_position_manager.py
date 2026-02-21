"""Tests for DCA Position Manager v2.0.

Tests deal lifecycle, safety orders, average entry calculation,
take-profit/stop-loss targets, and full buy→sell profit cycle.
"""

from decimal import Decimal

import pytest

from bot.strategies.dca.dca_position_manager import (
    CloseResult,
    DCAOrderConfig,
    DCAOrderStatus,
    DCAOrderType,
    DCAPositionManager,
    DealStatus,
)

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def config():
    return DCAOrderConfig(
        base_order_volume=Decimal("100"),
        max_safety_orders=5,
        volume_multiplier=Decimal("1.5"),
        price_step_pct=Decimal("2.0"),
        take_profit_pct=Decimal("3.0"),
        stop_loss_pct=Decimal("10.0"),
        max_position_cost=Decimal("5000"),
    )


@pytest.fixture
def manager(config):
    return DCAPositionManager(symbol="BTC/USDT", config=config)


@pytest.fixture
def deal(manager):
    return manager.open_deal(entry_price=Decimal("3100"))


# =========================================================================
# Config Validation Tests
# =========================================================================


class TestDCAOrderConfig:
    def test_defaults(self):
        cfg = DCAOrderConfig()
        cfg.validate()  # should not raise

    def test_invalid_base_volume(self):
        cfg = DCAOrderConfig(base_order_volume=Decimal("0"))
        with pytest.raises(ValueError, match="base_order_volume"):
            cfg.validate()

    def test_invalid_max_safety_orders(self):
        cfg = DCAOrderConfig(max_safety_orders=-1)
        with pytest.raises(ValueError, match="max_safety_orders"):
            cfg.validate()

    def test_invalid_volume_multiplier(self):
        cfg = DCAOrderConfig(volume_multiplier=Decimal("0"))
        with pytest.raises(ValueError, match="volume_multiplier"):
            cfg.validate()

    def test_invalid_price_step(self):
        cfg = DCAOrderConfig(price_step_pct=Decimal("0"))
        with pytest.raises(ValueError, match="price_step_pct"):
            cfg.validate()

    def test_invalid_take_profit(self):
        cfg = DCAOrderConfig(take_profit_pct=Decimal("-1"))
        with pytest.raises(ValueError, match="take_profit_pct"):
            cfg.validate()

    def test_invalid_stop_loss(self):
        cfg = DCAOrderConfig(stop_loss_pct=Decimal("0"))
        with pytest.raises(ValueError, match="stop_loss_pct"):
            cfg.validate()

    def test_invalid_max_position_cost(self):
        cfg = DCAOrderConfig(max_position_cost=Decimal("-100"))
        with pytest.raises(ValueError, match="max_position_cost"):
            cfg.validate()

    def test_total_required_capital(self, config):
        total = config.total_required_capital(Decimal("3100"))
        # base=100, SO1=150, SO2=225, SO3=337.5, SO4=506.25, SO5=759.375
        expected = (
            Decimal("100")
            + Decimal("150")
            + Decimal("225")
            + Decimal("337.5")
            + Decimal("506.25")
            + Decimal("759.375")
        )
        assert total == expected


# =========================================================================
# Open Deal Tests
# =========================================================================


class TestOpenDeal:
    def test_open_deal_basic(self, manager):
        deal = manager.open_deal(entry_price=Decimal("3100"))
        assert deal.status == DealStatus.ACTIVE
        assert deal.symbol == "BTC/USDT"
        assert deal.base_order_price == Decimal("3100")
        assert deal.average_entry_price == Decimal("3100")
        assert deal.total_cost > 0
        assert deal.total_volume > 0
        assert deal.safety_orders_filled == 0
        assert deal.max_safety_orders == 5
        assert deal.highest_price_since_entry == Decimal("3100")

    def test_base_order_volume_calculation(self, manager):
        deal = manager.open_deal(entry_price=Decimal("100"))
        # 100 USDT / 100 price = 1.0 volume
        assert deal.base_order_volume == Decimal("1.00000000")

    def test_next_safety_order_set(self, manager):
        deal = manager.open_deal(entry_price=Decimal("3100"))
        assert deal.next_safety_order_price is not None
        # SO1 at 2% drop: 3100 * 0.98 = 3038
        assert deal.next_safety_order_price == Decimal("3038.00")

    def test_base_order_recorded(self, manager):
        deal = manager.open_deal(entry_price=Decimal("3100"))
        orders = manager.get_deal_orders(deal.id)
        assert len(orders) == 1
        assert orders[0].order_type == DCAOrderType.BASE_ORDER
        assert orders[0].status == DCAOrderStatus.FILLED

    def test_deal_stored(self, manager):
        deal = manager.open_deal(entry_price=Decimal("3100"))
        retrieved = manager.get_deal(deal.id)
        assert retrieved is deal

    def test_zero_price_rejected(self, manager):
        with pytest.raises(ValueError, match="entry_price must be positive"):
            manager.open_deal(entry_price=Decimal("0"))

    def test_negative_price_rejected(self, manager):
        with pytest.raises(ValueError, match="entry_price must be positive"):
            manager.open_deal(entry_price=Decimal("-100"))

    def test_multiple_deals(self, manager):
        d1 = manager.open_deal(entry_price=Decimal("3100"))
        d2 = manager.open_deal(entry_price=Decimal("3200"))
        assert d1.id != d2.id
        assert len(manager.get_active_deals()) == 2

    def test_deal_to_dict(self, deal):
        d = deal.to_dict()
        assert d["symbol"] == "BTC/USDT"
        assert d["status"] == "active"
        assert d["safety_orders_filled"] == 0


# =========================================================================
# Safety Order Calculation Tests
# =========================================================================


class TestSafetyOrderCalculation:
    def test_safety_order_count(self, manager, deal):
        sos = manager.calculate_safety_orders(deal)
        assert len(sos) == 5

    def test_safety_order_prices(self, manager, deal):
        sos = manager.calculate_safety_orders(deal)
        # SO1: 3100 * (1 - 2/100) = 3038
        # SO2: 3100 * (1 - 4/100) = 2976
        # SO3: 3100 * (1 - 6/100) = 2914
        assert sos[0].price == Decimal("3038.00")
        assert sos[1].price == Decimal("2976.00")
        assert sos[2].price == Decimal("2914.00")

    def test_safety_order_prices_descending(self, manager, deal):
        sos = manager.calculate_safety_orders(deal)
        for i in range(1, len(sos)):
            assert sos[i].price < sos[i - 1].price

    def test_safety_order_volumes_increasing(self, manager, deal):
        sos = manager.calculate_safety_orders(deal)
        for i in range(1, len(sos)):
            assert sos[i].cost > sos[i - 1].cost

    def test_safety_order_volume_multiplier(self, manager, deal):
        sos = manager.calculate_safety_orders(deal)
        # SO1 cost = 100 * 1.5^1 = 150
        # SO2 cost = 100 * 1.5^2 = 225
        assert sos[0].cost == Decimal("150.0")
        assert sos[1].cost == Decimal("225.00")

    def test_safety_order_deviation_pct(self, manager, deal):
        sos = manager.calculate_safety_orders(deal)
        assert sos[0].price_deviation_pct == Decimal("2.0")
        assert sos[1].price_deviation_pct == Decimal("4.0")
        assert sos[4].price_deviation_pct == Decimal("10.0")

    def test_zero_safety_orders(self):
        cfg = DCAOrderConfig(max_safety_orders=0)
        mgr = DCAPositionManager(symbol="BTC/USDT", config=cfg)
        deal = mgr.open_deal(entry_price=Decimal("3100"))
        sos = mgr.calculate_safety_orders(deal)
        assert len(sos) == 0
        assert deal.next_safety_order_price is None


# =========================================================================
# Fill Safety Order Tests
# =========================================================================


class TestFillSafetyOrder:
    def test_fill_first_so(self, manager, deal):
        updated = manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        assert updated.safety_orders_filled == 1
        assert updated.total_volume > deal.base_order_volume
        assert updated.total_cost > deal.base_order_cost

    def test_average_entry_decreases(self, manager, deal):
        original_avg = deal.average_entry_price
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        assert deal.average_entry_price < original_avg

    def test_fill_multiple_sos(self, manager, deal):
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        manager.fill_safety_order(deal.id, level=2, fill_price=Decimal("2976"))
        assert deal.safety_orders_filled == 2
        # Average entry should be lower than both SO prices weighted
        assert deal.average_entry_price < Decimal("3100")

    def test_next_so_price_updated(self, manager, deal):
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        # Next should be SO2 price
        assert deal.next_safety_order_price == Decimal("2976.00")

    def test_last_so_clears_next_price(self, manager, deal):
        for level in range(1, 6):
            so_price = deal.base_order_price * (1 - Decimal("2.0") * level / 100)
            manager.fill_safety_order(deal.id, level=level, fill_price=so_price)
        assert deal.next_safety_order_price is None

    def test_wrong_level_rejected(self, manager, deal):
        with pytest.raises(ValueError, match="Expected SO level 1"):
            manager.fill_safety_order(deal.id, level=2, fill_price=Decimal("2976"))

    def test_exceeds_max_so(self, manager, deal):
        for level in range(1, 6):
            so_price = deal.base_order_price * (1 - Decimal("2.0") * level / 100)
            manager.fill_safety_order(deal.id, level=level, fill_price=so_price)
        with pytest.raises(ValueError, match="Max safety orders"):
            manager.fill_safety_order(deal.id, level=6, fill_price=Decimal("2500"))

    def test_closed_deal_rejected(self, manager, deal):
        manager.close_deal(deal.id, exit_price=Decimal("3200"), reason="take_profit")
        with pytest.raises(ValueError, match="not active"):
            manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))

    def test_so_order_recorded(self, manager, deal):
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        orders = manager.get_deal_orders(deal.id)
        assert len(orders) == 2  # base + SO1
        assert orders[1].order_type == DCAOrderType.SAFETY_ORDER

    def test_max_position_cost_check(self):
        cfg = DCAOrderConfig(
            base_order_volume=Decimal("1000"),
            max_safety_orders=5,
            volume_multiplier=Decimal("2.0"),
            price_step_pct=Decimal("2.0"),
            max_position_cost=Decimal("2000"),
        )
        mgr = DCAPositionManager(symbol="BTC/USDT", config=cfg)
        deal = mgr.open_deal(entry_price=Decimal("100"))
        # SO1 cost = 1000 * 2^1 = 2000, total would be 1000 + 2000 = 3000 > 2000
        with pytest.raises(ValueError, match="exceed max"):
            mgr.fill_safety_order(deal.id, level=1, fill_price=Decimal("98"))


# =========================================================================
# Close Deal Tests
# =========================================================================


class TestCloseDeal:
    def test_close_with_profit(self, manager, deal):
        result = manager.close_deal(deal.id, exit_price=Decimal("3200"), reason="take_profit")
        assert isinstance(result, CloseResult)
        assert result.realized_profit > 0
        assert result.realized_profit_pct > 0
        assert deal.status == DealStatus.CLOSED
        assert deal.close_reason == "take_profit"

    def test_close_with_loss(self, manager, deal):
        result = manager.close_deal(deal.id, exit_price=Decimal("2800"), reason="stop_loss")
        assert result.realized_profit < 0
        assert result.realized_profit_pct < 0

    def test_close_at_entry(self, manager, deal):
        result = manager.close_deal(deal.id, exit_price=Decimal("3100"), reason="manual")
        # Slight rounding may cause tiny difference
        assert abs(result.realized_profit) < Decimal("0.01")

    def test_close_after_safety_orders(self, manager, deal):
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        manager.fill_safety_order(deal.id, level=2, fill_price=Decimal("2976"))
        avg_entry = deal.average_entry_price

        # Close above average entry = profit
        result = manager.close_deal(
            deal.id, exit_price=avg_entry + Decimal("100"), reason="take_profit"
        )
        assert result.realized_profit > 0

    def test_close_records_sell_order(self, manager, deal):
        manager.close_deal(deal.id, exit_price=Decimal("3200"), reason="take_profit")
        orders = manager.get_deal_orders(deal.id)
        sell_orders = [o for o in orders if o.side == "sell"]
        assert len(sell_orders) == 1
        assert sell_orders[0].status == DCAOrderStatus.FILLED

    def test_close_already_closed(self, manager, deal):
        manager.close_deal(deal.id, exit_price=Decimal("3200"), reason="take_profit")
        with pytest.raises(ValueError, match="not active"):
            manager.close_deal(deal.id, exit_price=Decimal("3300"), reason="manual")

    def test_close_zero_price_rejected(self, manager, deal):
        with pytest.raises(ValueError, match="exit_price must be positive"):
            manager.close_deal(deal.id, exit_price=Decimal("0"), reason="manual")

    def test_cancel_deal(self, manager, deal):
        cancelled = manager.cancel_deal(deal.id)
        assert cancelled.status == DealStatus.CANCELLED
        assert cancelled.close_reason == "cancelled"


# =========================================================================
# Take Profit / Stop Loss Tests
# =========================================================================


class TestTPSL:
    def test_take_profit_price(self, manager, deal):
        tp = manager.get_take_profit_price(deal.id)
        # 3100 * 1.03 = 3193
        assert tp == Decimal("3193.00")

    def test_stop_loss_from_base(self, manager, deal):
        sl = manager.get_stop_loss_price(deal.id)
        # 3100 * 0.90 = 2790
        assert sl == Decimal("2790.00")

    def test_stop_loss_from_average(self):
        cfg = DCAOrderConfig(stop_loss_from_average=True, stop_loss_pct=Decimal("10.0"))
        mgr = DCAPositionManager(symbol="BTC/USDT", config=cfg)
        deal = mgr.open_deal(entry_price=Decimal("3100"))
        mgr.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        sl = mgr.get_stop_loss_price(deal.id)
        # SL from average entry (which is < 3100)
        assert sl < Decimal("2790")

    def test_tp_moves_down_with_sos(self, manager, deal):
        tp_before = manager.get_take_profit_price(deal.id)
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        tp_after = manager.get_take_profit_price(deal.id)
        assert tp_after < tp_before  # Average entry dropped


# =========================================================================
# Safety Order Trigger Tests
# =========================================================================


class TestSafetyOrderTrigger:
    def test_trigger_at_so_price(self, manager, deal):
        result = manager.check_safety_order_trigger(deal.id, Decimal("3038"))
        assert result is not None
        assert result.level == 1

    def test_no_trigger_above_price(self, manager, deal):
        result = manager.check_safety_order_trigger(deal.id, Decimal("3100"))
        assert result is None

    def test_trigger_below_so_price(self, manager, deal):
        result = manager.check_safety_order_trigger(deal.id, Decimal("3000"))
        assert result is not None
        assert result.level == 1

    def test_no_trigger_after_all_sos(self, manager, deal):
        for level in range(1, 6):
            so_price = deal.base_order_price * (1 - Decimal("2.0") * level / 100)
            manager.fill_safety_order(deal.id, level=level, fill_price=so_price)
        result = manager.check_safety_order_trigger(deal.id, Decimal("2000"))
        assert result is None

    def test_no_trigger_for_closed_deal(self, manager, deal):
        manager.close_deal(deal.id, exit_price=Decimal("3200"), reason="take_profit")
        result = manager.check_safety_order_trigger(deal.id, Decimal("2000"))
        assert result is None


# =========================================================================
# Profit Calculation Tests
# =========================================================================


class TestProfitCalculation:
    def test_profit_above_entry(self, manager, deal):
        profit, pct = manager.calculate_current_profit(deal.id, Decimal("3200"))
        assert profit > 0
        assert pct > 0

    def test_loss_below_entry(self, manager, deal):
        profit, pct = manager.calculate_current_profit(deal.id, Decimal("3000"))
        assert profit < 0
        assert pct < 0

    def test_breakeven(self, manager, deal):
        profit, pct = manager.calculate_current_profit(deal.id, Decimal("3100"))
        assert abs(pct) < Decimal("0.01")

    def test_profit_after_sos(self, manager, deal):
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        profit, pct = manager.calculate_current_profit(deal.id, deal.average_entry_price)
        assert abs(pct) < Decimal("0.01")


# =========================================================================
# Highest Price Tracking Tests
# =========================================================================


class TestHighestPriceTracking:
    def test_initial_highest(self, deal):
        assert deal.highest_price_since_entry == Decimal("3100")

    def test_update_new_high(self, manager, deal):
        updated = manager.update_highest_price(deal.id, Decimal("3200"))
        assert updated is True
        assert deal.highest_price_since_entry == Decimal("3200")

    def test_no_update_below_highest(self, manager, deal):
        manager.update_highest_price(deal.id, Decimal("3200"))
        updated = manager.update_highest_price(deal.id, Decimal("3150"))
        assert updated is False
        assert deal.highest_price_since_entry == Decimal("3200")

    def test_highest_not_reset_on_so(self, manager, deal):
        manager.update_highest_price(deal.id, Decimal("3200"))
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        # Highest should NOT be reset
        assert deal.highest_price_since_entry == Decimal("3200")


# =========================================================================
# Query Tests
# =========================================================================


class TestQueries:
    def test_get_active_deals(self, manager):
        d1 = manager.open_deal(entry_price=Decimal("3100"))
        d2 = manager.open_deal(entry_price=Decimal("3200"))
        assert len(manager.get_active_deals()) == 2
        manager.close_deal(d1.id, exit_price=Decimal("3200"), reason="tp")
        assert len(manager.get_active_deals()) == 1

    def test_get_closed_deals(self, manager):
        d1 = manager.open_deal(entry_price=Decimal("3100"))
        manager.close_deal(d1.id, exit_price=Decimal("3200"), reason="tp")
        assert len(manager.get_closed_deals()) == 1

    def test_total_realized_pnl(self, manager):
        d1 = manager.open_deal(entry_price=Decimal("3100"))
        d2 = manager.open_deal(entry_price=Decimal("3200"))
        manager.close_deal(d1.id, exit_price=Decimal("3200"), reason="tp")
        manager.close_deal(d2.id, exit_price=Decimal("3100"), reason="sl")
        pnl = manager.total_realized_pnl
        # d1 profit, d2 loss — should sum
        assert isinstance(pnl, Decimal)

    def test_get_deal_not_found(self, manager):
        with pytest.raises(KeyError, match="not found"):
            manager.get_deal("NONEXISTENT")


# =========================================================================
# Statistics Tests
# =========================================================================


class TestStatistics:
    def test_statistics_empty(self, manager):
        stats = manager.get_statistics()
        assert stats["total_deals"] == 0
        assert stats["active_deals"] == 0
        assert stats["win_rate"] == "N/A"

    def test_statistics_with_deals(self, manager):
        d1 = manager.open_deal(entry_price=Decimal("3100"))
        d2 = manager.open_deal(entry_price=Decimal("3200"))
        manager.close_deal(d1.id, exit_price=Decimal("3200"), reason="tp")
        stats = manager.get_statistics()
        assert stats["total_deals"] == 2
        assert stats["active_deals"] == 1
        assert stats["closed_deals"] == 1
        assert stats["winning_deals"] == 1
        assert stats["symbol"] == "BTC/USDT"


# =========================================================================
# Full Lifecycle Integration Tests
# =========================================================================


class TestFullLifecycle:
    def test_base_order_to_take_profit(self, manager):
        """Open deal → price rises → close at TP."""
        deal = manager.open_deal(entry_price=Decimal("3100"))
        tp_price = manager.get_take_profit_price(deal.id)
        result = manager.close_deal(deal.id, exit_price=tp_price, reason="take_profit")
        assert result.realized_profit > 0
        assert result.realized_profit_pct > Decimal("2.9")  # ~3%

    def test_safety_orders_then_take_profit(self, manager):
        """Open → price drops → SOs fill → price rises → TP."""
        deal = manager.open_deal(entry_price=Decimal("3100"))

        # Price drops, fill SOs
        manager.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        manager.fill_safety_order(deal.id, level=2, fill_price=Decimal("2976"))

        # Average entry should be lower
        avg = deal.average_entry_price
        assert avg < Decimal("3100")

        # Price recovers to TP
        tp = manager.get_take_profit_price(deal.id)
        result = manager.close_deal(deal.id, exit_price=tp, reason="take_profit")
        assert result.realized_profit > 0

    def test_stop_loss_after_all_sos(self, manager):
        """Open → all SOs fill → price keeps dropping → SL."""
        deal = manager.open_deal(entry_price=Decimal("3100"))

        for level in range(1, 6):
            so_price = deal.base_order_price * (1 - Decimal("2.0") * level / 100)
            manager.fill_safety_order(deal.id, level=level, fill_price=so_price)

        sl = manager.get_stop_loss_price(deal.id)
        result = manager.close_deal(deal.id, exit_price=sl, reason="stop_loss")
        assert result.realized_profit < 0

    def test_multiple_concurrent_deals(self, manager):
        """Multiple deals running simultaneously."""
        d1 = manager.open_deal(entry_price=Decimal("3100"))
        d2 = manager.open_deal(entry_price=Decimal("50000"))

        manager.fill_safety_order(d1.id, level=1, fill_price=Decimal("3038"))

        r1 = manager.close_deal(d1.id, exit_price=Decimal("3200"), reason="tp")
        r2 = manager.close_deal(d2.id, exit_price=Decimal("49000"), reason="sl")

        assert r1.realized_profit > 0
        assert r2.realized_profit < 0
        assert len(manager.get_active_deals()) == 0
        assert len(manager.get_closed_deals()) == 2
