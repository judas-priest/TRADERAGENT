"""Tests for GridEngine"""

from decimal import Decimal

import pytest

from bot.core.grid_engine import GridEngine, GridOrder, GridType


class TestGridEngine:
    """Test GridEngine functionality"""

    def test_init_valid_params(self):
        """Test initialization with valid parameters"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=10,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        assert engine.symbol == "BTC/USDT"
        assert engine.upper_price == Decimal("50000")
        assert engine.lower_price == Decimal("40000")
        assert engine.grid_levels == 10
        assert engine.amount_per_grid == Decimal("100")
        assert engine.profit_per_grid == Decimal("0.01")
        assert engine.grid_type == GridType.STATIC

    def test_init_invalid_price_boundaries(self):
        """Test initialization with invalid price boundaries"""
        with pytest.raises(ValueError, match="upper_price must be greater"):
            GridEngine(
                symbol="BTC/USDT",
                upper_price=Decimal("40000"),
                lower_price=Decimal("50000"),
                grid_levels=10,
                amount_per_grid=Decimal("100"),
                profit_per_grid=Decimal("0.01"),
            )

    def test_init_invalid_grid_levels(self):
        """Test initialization with invalid grid levels"""
        with pytest.raises(ValueError, match="grid_levels must be at least 2"):
            GridEngine(
                symbol="BTC/USDT",
                upper_price=Decimal("50000"),
                lower_price=Decimal("40000"),
                grid_levels=1,
                amount_per_grid=Decimal("100"),
                profit_per_grid=Decimal("0.01"),
            )

    def test_init_invalid_amount(self):
        """Test initialization with invalid amount"""
        with pytest.raises(ValueError, match="amount_per_grid must be positive"):
            GridEngine(
                symbol="BTC/USDT",
                upper_price=Decimal("50000"),
                lower_price=Decimal("40000"),
                grid_levels=10,
                amount_per_grid=Decimal("-100"),
                profit_per_grid=Decimal("0.01"),
            )

    def test_calculate_grid_levels(self):
        """Test grid level calculation"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        levels = engine.calculate_grid_levels()

        assert len(levels) == 5
        assert levels[0] == Decimal("40000")
        assert levels[-1] == Decimal("50000")
        # Check equal spacing
        expected_step = Decimal("2500")
        for i in range(1, len(levels)):
            assert abs(levels[i] - levels[i - 1] - expected_step) < Decimal("0.01")

    def test_initialize_grid_with_current_price(self):
        """Test grid initialization with current price"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        current_price = Decimal("45000")
        orders = engine.initialize_grid(current_price)

        # Should have buy orders below current price and sell orders above
        buy_orders = [o for o in orders if o.side == "buy"]
        sell_orders = [o for o in orders if o.side == "sell"]

        assert len(buy_orders) > 0
        assert len(sell_orders) > 0

        # All buy orders should be below current price
        for order in buy_orders:
            assert order.price < current_price

        # All sell orders should be above current price
        for order in sell_orders:
            assert order.price > current_price

    def test_register_order(self):
        """Test order registration"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        order = GridOrder(
            level=1,
            price=Decimal("42000"),
            amount=Decimal("100"),
            side="buy",
        )

        engine.register_order(order, "order123")

        assert order.order_id == "order123"
        assert "order123" in engine.active_orders
        assert engine.active_orders["order123"] == order

    def test_handle_order_filled_buy(self):
        """Test handling of filled buy order"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        buy_order = GridOrder(
            level=1,
            price=Decimal("42000"),
            amount=Decimal("100"),
            side="buy",
        )
        engine.register_order(buy_order, "order123")

        rebalance_order = engine.handle_order_filled(
            "order123", Decimal("42000"), Decimal("100")
        )

        assert rebalance_order is not None
        assert rebalance_order.side == "sell"
        assert rebalance_order.price > buy_order.price
        assert engine.buy_count == 1
        assert "order123" not in engine.active_orders
        assert buy_order in engine.filled_orders

    def test_handle_order_filled_sell(self):
        """Test handling of filled sell order"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        sell_order = GridOrder(
            level=3,
            price=Decimal("48000"),
            amount=Decimal("100"),
            side="sell",
        )
        engine.register_order(sell_order, "order456")

        rebalance_order = engine.handle_order_filled(
            "order456", Decimal("48000"), Decimal("100")
        )

        assert rebalance_order is not None
        assert rebalance_order.side == "buy"
        assert rebalance_order.price < sell_order.price
        assert engine.sell_count == 1
        assert engine.total_profit > 0
        assert "order456" not in engine.active_orders

    def test_handle_order_filled_nonexistent(self):
        """Test handling of non-existent order"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        rebalance_order = engine.handle_order_filled(
            "nonexistent", Decimal("42000"), Decimal("100")
        )

        assert rebalance_order is None

    def test_update_grid_bounds_dynamic(self):
        """Test updating grid bounds for dynamic grid"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
            grid_type=GridType.DYNAMIC,
        )

        # Initialize grid first
        engine.initialize_grid(Decimal("45000"))

        # Add some active orders
        order1 = GridOrder(1, Decimal("42000"), Decimal("100"), "buy")
        order2 = GridOrder(2, Decimal("44000"), Decimal("100"), "buy")
        engine.register_order(order1, "order1")
        engine.register_order(order2, "order2")

        # Update bounds
        orders_to_cancel, new_orders = engine.update_grid_bounds(
            Decimal("55000"), Decimal("45000"), Decimal("50000")
        )

        assert len(orders_to_cancel) == 2
        assert "order1" in orders_to_cancel
        assert "order2" in orders_to_cancel
        assert len(new_orders) > 0
        assert engine.upper_price == Decimal("55000")
        assert engine.lower_price == Decimal("45000")

    def test_update_grid_bounds_static_fails(self):
        """Test that static grid cannot update bounds"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
            grid_type=GridType.STATIC,
        )

        orders_to_cancel, new_orders = engine.update_grid_bounds(
            Decimal("55000"), Decimal("45000"), Decimal("50000")
        )

        assert len(orders_to_cancel) == 0
        assert len(new_orders) == 0
        # Bounds should not change
        assert engine.upper_price == Decimal("50000")
        assert engine.lower_price == Decimal("40000")

    def test_get_grid_status(self):
        """Test getting grid status"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        status = engine.get_grid_status()

        assert status["symbol"] == "BTC/USDT"
        assert status["grid_type"] == GridType.STATIC
        assert status["upper_price"] == 50000.0
        assert status["lower_price"] == 40000.0
        assert status["grid_levels"] == 5
        assert status["active_orders"] == 0
        assert status["filled_orders"] == 0
        assert status["total_profit"] == 0.0
        assert status["buy_count"] == 0
        assert status["sell_count"] == 0

    def test_cancel_order(self):
        """Test order cancellation"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        order = GridOrder(1, Decimal("42000"), Decimal("100"), "buy")
        engine.register_order(order, "order123")

        result = engine.cancel_order("order123")

        assert result is True
        assert "order123" not in engine.active_orders

    def test_cancel_nonexistent_order(self):
        """Test cancelling non-existent order"""
        engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        result = engine.cancel_order("nonexistent")

        assert result is False

    def test_grid_order_repr(self):
        """Test GridOrder string representation"""
        order = GridOrder(
            level=1,
            price=Decimal("42000"),
            amount=Decimal("100"),
            side="buy",
            order_id="order123",
            filled=False,
        )

        repr_str = repr(order)

        assert "GridOrder" in repr_str
        assert "level=1" in repr_str
        assert "side=buy" in repr_str
        assert "filled=False" in repr_str
