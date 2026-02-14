"""Tests for GridOrderManager v2.0.

Tests order lifecycle, counter-orders, partial fills, rebalancing, and profit tracking.
"""

from decimal import Decimal

import pytest

from bot.strategies.grid.grid_calculator import GridConfig, GridLevel, GridSpacing
from bot.strategies.grid.grid_order_manager import (
    GridCycle,
    GridOrderManager,
    GridOrderState,
    OrderStatus,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def manager():
    return GridOrderManager(symbol="BTC/USDT")


@pytest.fixture
def config():
    return GridConfig(
        upper_price=Decimal("50000"),
        lower_price=Decimal("40000"),
        num_levels=11,
        spacing=GridSpacing.ARITHMETIC,
        amount_per_grid=Decimal("100"),
        profit_per_grid=Decimal("0.01"),  # 1% profit per grid
    )


@pytest.fixture
def initialized_manager(manager, config):
    """Manager with initial orders calculated."""
    manager.calculate_initial_orders(config, Decimal("45000"))
    return manager


# =========================================================================
# GridOrderState Tests
# =========================================================================


class TestGridOrderState:
    def test_initial_state(self):
        level = GridLevel(0, Decimal("44000"), "buy", Decimal("0.002"))
        state = GridOrderState(id="test-1", grid_level=level, remaining_amount=level.amount)
        assert state.status == OrderStatus.PENDING
        assert state.filled_amount == Decimal("0")
        assert not state.is_active
        assert state.fill_pct == 0.0

    def test_is_active_open(self):
        level = GridLevel(0, Decimal("44000"), "buy", Decimal("0.002"))
        state = GridOrderState(id="test-1", grid_level=level)
        state.status = OrderStatus.OPEN
        assert state.is_active is True

    def test_is_active_partial(self):
        level = GridLevel(0, Decimal("44000"), "buy", Decimal("0.002"))
        state = GridOrderState(id="test-1", grid_level=level)
        state.status = OrderStatus.PARTIALLY_FILLED
        assert state.is_active is True

    def test_not_active_filled(self):
        level = GridLevel(0, Decimal("44000"), "buy", Decimal("0.002"))
        state = GridOrderState(id="test-1", grid_level=level)
        state.status = OrderStatus.FILLED
        assert state.is_active is False

    def test_fill_pct(self):
        level = GridLevel(0, Decimal("44000"), "buy", Decimal("1.0"))
        state = GridOrderState(id="test-1", grid_level=level)
        state.filled_amount = Decimal("0.5")
        assert state.fill_pct == 50.0

    def test_to_dict(self):
        level = GridLevel(0, Decimal("44000"), "buy", Decimal("0.002"))
        state = GridOrderState(
            id="test-1",
            grid_level=level,
            exchange_order_id="EX-123",
        )
        state.status = OrderStatus.OPEN
        d = state.to_dict()
        assert d["id"] == "test-1"
        assert d["exchange_order_id"] == "EX-123"
        assert d["status"] == "open"
        assert d["side"] == "buy"
        assert d["price"] == "44000"


# =========================================================================
# Initialization Tests
# =========================================================================


class TestInitialization:
    def test_calculate_initial_orders(self, manager, config):
        orders = manager.calculate_initial_orders(config, Decimal("45000"))
        assert len(orders) > 0
        buys = [o for o in orders if o.grid_level.side == "buy"]
        sells = [o for o in orders if o.grid_level.side == "sell"]
        assert len(buys) > 0
        assert len(sells) > 0

    def test_all_orders_pending(self, manager, config):
        orders = manager.calculate_initial_orders(config, Decimal("45000"))
        for o in orders:
            assert o.status == OrderStatus.PENDING

    def test_config_stored(self, manager, config):
        manager.calculate_initial_orders(config, Decimal("45000"))
        assert manager._config is config

    def test_invalid_config_raises(self, manager):
        bad_config = GridConfig(
            upper_price=Decimal("40000"),
            lower_price=Decimal("50000"),
            num_levels=10,
        )
        with pytest.raises(ValueError):
            manager.calculate_initial_orders(bad_config, Decimal("45000"))

    def test_orders_have_unique_ids(self, manager, config):
        orders = manager.calculate_initial_orders(config, Decimal("45000"))
        ids = [o.id for o in orders]
        assert len(ids) == len(set(ids))


# =========================================================================
# Order Registration Tests
# =========================================================================


class TestOrderRegistration:
    def test_register_exchange_order(self, initialized_manager):
        pending = initialized_manager.pending_orders
        assert len(pending) > 0
        order = pending[0]
        initialized_manager.register_exchange_order(order.id, "EX-001")
        assert order.status == OrderStatus.OPEN
        assert order.exchange_order_id == "EX-001"
        assert initialized_manager._total_orders_placed == 1

    def test_register_unknown_order(self, initialized_manager):
        # Should not raise
        initialized_manager.register_exchange_order("nonexistent", "EX-999")
        assert initialized_manager._total_orders_placed == 0

    def test_mark_order_failed(self, initialized_manager):
        pending = initialized_manager.pending_orders
        order = pending[0]
        initialized_manager.mark_order_failed(order.id, "insufficient funds")
        assert order.status == OrderStatus.FAILED
        assert initialized_manager._failed_orders == 1

    def test_mark_unknown_order_failed(self, initialized_manager):
        # Should not raise
        initialized_manager.mark_order_failed("nonexistent")
        assert initialized_manager._failed_orders == 0


# =========================================================================
# Order Fill Tests
# =========================================================================


class TestOrderFill:
    def _place_order(self, manager, order):
        """Helper: register order on exchange."""
        exchange_id = f"EX-{order.id[:6]}"
        manager.register_exchange_order(order.id, exchange_id)
        return exchange_id

    def test_full_fill_buy(self, initialized_manager):
        buys = [o for o in initialized_manager.pending_orders if o.grid_level.side == "buy"]
        order = buys[0]
        ex_id = self._place_order(initialized_manager, order)

        counter = initialized_manager.on_order_filled(
            ex_id, order.grid_level.price, order.grid_level.amount
        )

        assert order.status == OrderStatus.FILLED
        assert counter is not None
        assert counter.grid_level.side == "sell"  # counter of buy
        assert counter.status == OrderStatus.PENDING
        assert initialized_manager._total_fills == 1

    def test_full_fill_sell(self, initialized_manager):
        sells = [o for o in initialized_manager.pending_orders if o.grid_level.side == "sell"]
        order = sells[0]
        ex_id = self._place_order(initialized_manager, order)

        counter = initialized_manager.on_order_filled(
            ex_id, order.grid_level.price, order.grid_level.amount
        )

        assert order.status == OrderStatus.FILLED
        assert counter is not None
        assert counter.grid_level.side == "buy"  # counter of sell
        assert counter.status == OrderStatus.PENDING

    def test_counter_order_price_with_profit(self, initialized_manager):
        buys = [o for o in initialized_manager.pending_orders if o.grid_level.side == "buy"]
        order = buys[0]
        ex_id = self._place_order(initialized_manager, order)

        fill_price = Decimal("44000")
        counter = initialized_manager.on_order_filled(
            ex_id, fill_price, order.grid_level.amount
        )

        # Counter sell price should be fill_price * 1.01 (1% profit)
        expected_price = (fill_price * Decimal("1.01")).quantize(Decimal("0.01"))
        assert counter.grid_level.price == expected_price

    def test_unknown_exchange_order_fill(self, initialized_manager):
        result = initialized_manager.on_order_filled(
            "UNKNOWN-ID", Decimal("45000"), Decimal("0.1")
        )
        assert result is None

    def test_partial_fill(self, initialized_manager):
        buys = [o for o in initialized_manager.pending_orders if o.grid_level.side == "buy"]
        order = buys[0]
        ex_id = self._place_order(initialized_manager, order)

        initialized_manager.on_order_partially_filled(
            ex_id, Decimal("44000"), Decimal("0.001"), Decimal("0.001")
        )

        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_amount == Decimal("0.001")
        assert order.remaining_amount == Decimal("0.001")
        assert initialized_manager._partial_fills == 1

    def test_partial_fill_unknown(self, initialized_manager):
        # Should not raise
        initialized_manager.on_order_partially_filled(
            "UNKNOWN", Decimal("44000"), Decimal("0.001"), Decimal("0.001")
        )
        assert initialized_manager._partial_fills == 0


# =========================================================================
# Profit Tracking Tests
# =========================================================================


class TestProfitTracking:
    def _place_order(self, manager, order):
        exchange_id = f"EX-{order.id[:6]}"
        manager.register_exchange_order(order.id, exchange_id)
        return exchange_id

    def test_buy_sell_cycle_profit(self, initialized_manager):
        buys = [o for o in initialized_manager.pending_orders if o.grid_level.side == "buy"]
        buy_order = buys[0]
        buy_ex_id = self._place_order(initialized_manager, buy_order)

        # Fill buy at 44000
        buy_price = Decimal("44000")
        buy_amount = Decimal("0.002")
        counter_sell = initialized_manager.on_order_filled(
            buy_ex_id, buy_price, buy_amount
        )

        # Now place and fill the counter sell
        sell_ex_id = self._place_order(initialized_manager, counter_sell)
        sell_price = counter_sell.grid_level.price  # 44000 * 1.01 = 44440
        initialized_manager.on_order_filled(sell_ex_id, sell_price, buy_amount)

        # Check profit
        completed = initialized_manager.completed_cycles
        assert len(completed) == 1
        expected_profit = (sell_price - buy_price) * buy_amount
        assert completed[0].profit == expected_profit
        assert initialized_manager.total_realized_pnl == expected_profit

    def test_no_completed_cycles_initially(self, initialized_manager):
        assert len(initialized_manager.completed_cycles) == 0
        assert initialized_manager.total_realized_pnl == Decimal("0")

    def test_sell_creates_pending_cycle(self, initialized_manager):
        sells = [o for o in initialized_manager.pending_orders if o.grid_level.side == "sell"]
        sell_order = sells[0]
        sell_ex_id = self._place_order(initialized_manager, sell_order)

        initialized_manager.on_order_filled(
            sell_ex_id, sell_order.grid_level.price, sell_order.grid_level.amount
        )

        # Sell without matching buy creates an incomplete cycle
        assert len(initialized_manager._cycles) == 1
        assert not initialized_manager._cycles[0].completed


# =========================================================================
# Rebalancing Tests
# =========================================================================


class TestRebalancing:
    def _place_all(self, manager):
        """Place all pending orders."""
        for order in list(manager.pending_orders):
            ex_id = f"EX-{order.id[:6]}"
            manager.register_exchange_order(order.id, ex_id)

    def test_get_orders_to_cancel(self, initialized_manager):
        self._place_all(initialized_manager)
        to_cancel = initialized_manager.get_orders_to_cancel()
        assert len(to_cancel) > 0
        for o in to_cancel:
            assert o.is_active

    def test_mark_order_cancelled(self, initialized_manager):
        self._place_all(initialized_manager)
        active = initialized_manager.active_orders
        order = active[0]
        initialized_manager.mark_order_cancelled(order.id)
        assert order.status == OrderStatus.CANCELLED
        assert not order.is_active

    def test_rebalance(self, initialized_manager, config):
        self._place_all(initialized_manager)
        initial_active = len(initialized_manager.active_orders)
        assert initial_active > 0

        new_config = GridConfig(
            upper_price=Decimal("52000"),
            lower_price=Decimal("42000"),
            num_levels=11,
            spacing=GridSpacing.ARITHMETIC,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        cancelled, new_orders = initialized_manager.rebalance(
            new_config, Decimal("47000")
        )

        assert len(cancelled) == initial_active
        assert len(new_orders) > 0
        # All cancelled should be cancelled status
        for o in cancelled:
            assert o.status == OrderStatus.CANCELLED
        # New orders are pending
        for o in new_orders:
            assert o.status == OrderStatus.PENDING

    def test_rebalance_updates_config(self, initialized_manager):
        new_config = GridConfig(
            upper_price=Decimal("55000"),
            lower_price=Decimal("35000"),
            num_levels=21,
            spacing=GridSpacing.GEOMETRIC,
            amount_per_grid=Decimal("50"),
        )
        initialized_manager.rebalance(new_config, Decimal("45000"))
        assert initialized_manager._config is new_config


# =========================================================================
# Query Methods Tests
# =========================================================================


class TestQueryMethods:
    def _place_all(self, manager):
        for order in list(manager.pending_orders):
            ex_id = f"EX-{order.id[:6]}"
            manager.register_exchange_order(order.id, ex_id)

    def test_active_orders(self, initialized_manager):
        self._place_all(initialized_manager)
        active = initialized_manager.active_orders
        assert len(active) > 0
        for o in active:
            assert o.is_active

    def test_pending_orders(self, initialized_manager):
        pending = initialized_manager.pending_orders
        assert len(pending) > 0
        for o in pending:
            assert o.status == OrderStatus.PENDING

    def test_filled_orders_empty_initially(self, initialized_manager):
        assert len(initialized_manager.filled_orders) == 0

    def test_get_order_by_exchange_id(self, initialized_manager):
        pending = initialized_manager.pending_orders
        order = pending[0]
        initialized_manager.register_exchange_order(order.id, "EX-LOOKUP")
        found = initialized_manager.get_order_by_exchange_id("EX-LOOKUP")
        assert found is not None
        assert found.id == order.id

    def test_get_order_by_unknown_exchange_id(self, initialized_manager):
        assert initialized_manager.get_order_by_exchange_id("NOPE") is None


# =========================================================================
# Statistics Tests
# =========================================================================


class TestStatistics:
    def test_initial_stats(self, manager):
        stats = manager.get_statistics()
        assert stats["symbol"] == "BTC/USDT"
        assert stats["total_orders"] == 0
        assert stats["active_orders"] == 0
        assert stats["total_realized_pnl"] == "0"

    def test_stats_after_init(self, initialized_manager):
        stats = initialized_manager.get_statistics()
        assert stats["total_orders"] > 0
        assert stats["pending_orders"] > 0
        assert stats["active_orders"] == 0

    def test_stats_after_placement(self, initialized_manager):
        for order in list(initialized_manager.pending_orders):
            initialized_manager.register_exchange_order(
                order.id, f"EX-{order.id[:6]}"
            )
        stats = initialized_manager.get_statistics()
        assert stats["active_orders"] > 0
        assert stats["total_orders_placed"] > 0

    def test_stats_grid_config(self, initialized_manager):
        stats = initialized_manager.get_statistics()
        assert stats["grid_config"]["spacing"] == "arithmetic"
        assert stats["grid_config"]["num_levels"] == 11


# =========================================================================
# Integration Test — Full Lifecycle
# =========================================================================


class TestFullLifecycle:
    def test_init_place_fill_counter_cycle(self):
        """Test the complete grid lifecycle: init → place → fill → counter → profit."""
        manager = GridOrderManager(symbol="ETH/USDT")
        config = GridConfig(
            upper_price=Decimal("4000"),
            lower_price=Decimal("3000"),
            num_levels=11,
            spacing=GridSpacing.ARITHMETIC,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        # 1. Calculate initial orders
        orders = manager.calculate_initial_orders(config, Decimal("3500"))
        buys = [o for o in orders if o.grid_level.side == "buy"]
        sells = [o for o in orders if o.grid_level.side == "sell"]
        assert len(buys) > 0
        assert len(sells) > 0

        # 2. Place all orders
        for order in orders:
            manager.register_exchange_order(order.id, f"EX-{order.id[:6]}")
        assert len(manager.active_orders) == len(orders)

        # 3. Buy order gets filled
        buy = buys[0]
        fill_price = buy.grid_level.price
        fill_amount = buy.grid_level.amount
        counter_sell = manager.on_order_filled(
            buy.exchange_order_id, fill_price, fill_amount
        )
        assert counter_sell is not None
        assert counter_sell.grid_level.side == "sell"
        assert manager._total_fills == 1

        # 4. Place counter sell
        manager.register_exchange_order(counter_sell.id, f"EX-{counter_sell.id[:6]}")

        # 5. Counter sell gets filled
        sell_price = counter_sell.grid_level.price
        counter_buy = manager.on_order_filled(
            counter_sell.exchange_order_id, sell_price, fill_amount
        )
        assert counter_buy is not None
        assert counter_buy.grid_level.side == "buy"
        assert manager._total_fills == 2

        # 6. Verify profit
        completed = manager.completed_cycles
        assert len(completed) == 1
        assert completed[0].profit > 0
        assert manager.total_realized_pnl > 0

        # 7. Check statistics
        stats = manager.get_statistics()
        assert stats["total_fills"] == 2
        assert stats["completed_cycles"] == 1
