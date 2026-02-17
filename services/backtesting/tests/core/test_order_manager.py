"""Tests for GridOrderManager."""

from decimal import Decimal

import pytest

from grid_backtester.core.calculator import GridConfig, GridSpacing
from grid_backtester.core.order_manager import (
    GridCycle,
    GridOrderManager,
    GridOrderState,
    OrderStatus,
)


class TestGridOrderManager:

    def test_initial_orders(self):
        mgr = GridOrderManager(symbol="BTCUSDT")
        config = GridConfig(
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            amount_per_grid=Decimal("100"),
        )
        orders = mgr.calculate_initial_orders(config, Decimal("45000"))

        assert len(orders) > 0
        for o in orders:
            assert o.status == OrderStatus.PENDING

    def test_register_and_fill(self):
        mgr = GridOrderManager(symbol="BTCUSDT")
        config = GridConfig(
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=5,
            amount_per_grid=Decimal("100"),
        )
        orders = mgr.calculate_initial_orders(config, Decimal("45000"))

        # Register first order
        first = orders[0]
        mgr.register_exchange_order(first.id, "ex_001")
        assert first.status == OrderStatus.OPEN

        # Fill it
        counter = mgr.on_order_filled(
            exchange_order_id="ex_001",
            filled_price=first.grid_level.price,
            filled_amount=first.grid_level.amount,
        )
        assert first.status == OrderStatus.FILLED
        assert counter is not None
        assert counter.grid_level.side != first.grid_level.side

    def test_rebalance(self):
        mgr = GridOrderManager(symbol="BTCUSDT")
        config = GridConfig(
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=5,
            amount_per_grid=Decimal("100"),
        )
        mgr.calculate_initial_orders(config, Decimal("45000"))

        # Register orders as open
        for o in list(mgr._orders.values())[:3]:
            mgr.register_exchange_order(o.id, f"ex_{o.id}")

        new_config = GridConfig(
            upper_price=Decimal("47000"),
            lower_price=Decimal("45000"),
            num_levels=5,
            amount_per_grid=Decimal("100"),
        )
        cancelled, new_orders = mgr.rebalance(new_config, Decimal("46000"))

        assert len(cancelled) > 0
        assert len(new_orders) > 0

    def test_statistics(self):
        mgr = GridOrderManager(symbol="BTCUSDT")
        config = GridConfig(
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=5,
            amount_per_grid=Decimal("100"),
        )
        mgr.calculate_initial_orders(config, Decimal("45000"))
        stats = mgr.get_statistics()

        assert stats["symbol"] == "BTCUSDT"
        assert stats["total_orders"] > 0
