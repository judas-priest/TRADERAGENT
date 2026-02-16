"""Integration tests for trading modules"""

from decimal import Decimal

from bot.core import DCAEngine, GridEngine, RiskManager


class TestGridDCAIntegration:
    """Test integration between GridEngine and DCAEngine"""

    def test_hybrid_strategy_workflow(self):
        """Test a hybrid grid+DCA strategy workflow"""
        # Initialize engines
        grid = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        dca = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=3,
            take_profit_percentage=Decimal("0.1"),
        )

        # Initialize grid at current price
        current_price = Decimal("45000")
        grid_orders = grid.initialize_grid(current_price)

        assert len(grid_orders) > 0

        # Start DCA position
        dca.execute_dca_step(current_price)

        assert dca.position is not None
        assert dca.position.entry_price == current_price

        # Price drops - both grid and DCA should react
        new_price = Decimal("42750")  # 5% drop

        # DCA should trigger
        actions = dca.update_price(new_price)
        assert actions["dca_triggered"] is True

        # Grid should have some buy orders at this level
        buy_orders = [o for o in grid_orders if o.side == "buy" and o.price <= new_price]
        assert len(buy_orders) > 0


class TestGridRiskIntegration:
    """Test integration between GridEngine and RiskManager"""

    def test_risk_limits_grid_orders(self):
        """Test that RiskManager properly limits GridEngine orders"""
        grid = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=10,
            amount_per_grid=Decimal("2000"),  # Amount per grid in USDT
            profit_per_grid=Decimal("0.01"),
        )

        risk = RiskManager(
            max_position_size=Decimal("10000"),
            min_order_size=Decimal("10"),
        )

        risk.initialize_balance(Decimal("10000"))

        # Initialize grid
        grid_orders = grid.initialize_grid(Decimal("45000"))

        # Check each order against risk limits
        current_position = Decimal("0")
        allowed_orders = 0

        for order in grid_orders:
            order_value = order.price * order.amount
            check = risk.check_trade(
                order_value,
                current_position,
                Decimal("10000") - current_position,
            )

            if check.allowed:
                allowed_orders += 1
                current_position += order_value
            else:
                break

        # Should allow some orders but not all due to position limits
        assert allowed_orders > 0
        assert allowed_orders < len(grid_orders)

    def test_risk_halts_trading(self):
        """Test that RiskManager halts all trading on stop-loss"""
        grid = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        risk = RiskManager(
            max_position_size=Decimal("10000"),
            min_order_size=Decimal("10"),
            stop_loss_percentage=Decimal("0.15"),
        )

        risk.initialize_balance(Decimal("10000"))

        # Trigger stop-loss
        risk.update_balance(Decimal("8500"))

        assert risk.is_halted is True

        # Try to place grid orders - should all be rejected
        grid_orders = grid.initialize_grid(Decimal("45000"))

        for order in grid_orders:
            order_value = order.price * order.amount
            check = risk.check_trade(order_value, Decimal("0"), Decimal("10000"))

            assert check.allowed is False


class TestDCARiskIntegration:
    """Test integration between DCAEngine and RiskManager"""

    def test_risk_limits_dca_steps(self):
        """Test that RiskManager limits DCA step execution"""
        dca = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("5000"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        risk = RiskManager(
            max_position_size=Decimal("10000"),
            min_order_size=Decimal("10"),
        )

        risk.initialize_balance(Decimal("10000"))

        # Execute first DCA step
        dca.execute_dca_step(Decimal("40000"))

        # Check if we can execute second step (order value = 5000)
        order_value = Decimal("5000")
        current_position = Decimal("5000")
        available_balance = Decimal("5000")

        check = risk.check_trade(order_value, current_position, available_balance)

        # Should be allowed (total would be 10000, at the limit)
        assert check.allowed is True

        # Try third step - should fail due to position limit
        check = risk.check_trade(
            order_value,
            Decimal("10000"),
            available_balance,
        )

        assert check.allowed is False

    def test_dca_with_daily_loss_limit(self):
        """Test DCA behavior with daily loss limits"""
        dca = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        risk = RiskManager(
            max_position_size=Decimal("10000"),
            min_order_size=Decimal("10"),
            max_daily_loss=Decimal("500"),
        )

        risk.initialize_balance(Decimal("10000"))

        # Execute DCA steps
        dca.execute_dca_step(Decimal("40000"))
        dca.execute_dca_step(Decimal("38000"))

        # Simulate daily loss
        risk.update_balance(Decimal("9700"))
        risk.update_balance(Decimal("9500"))

        assert risk.is_halted is True

        # Further DCA attempts should be blocked by risk manager
        if dca.check_dca_trigger(Decimal("36000")):
            check = risk.check_trade(Decimal("100"), Decimal("200"), Decimal("9500"))
            assert check.allowed is False


class TestFullStrategyIntegration:
    """Test full strategy with all three modules"""

    def test_complete_trading_cycle(self):
        """Test a complete trading cycle with grid, DCA, and risk management"""
        # Initialize all modules
        grid = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),  # Amount per grid in USDT
            profit_per_grid=Decimal("0.01"),
        )

        dca = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("0.01"),  # Amount in base currency (BTC)
            max_steps=3,
            take_profit_percentage=Decimal("0.1"),
        )

        risk = RiskManager(
            max_position_size=Decimal("5000"),
            min_order_size=Decimal("10"),
            stop_loss_percentage=Decimal("0.2"),
        )

        risk.initialize_balance(Decimal("10000"))

        # Step 1: Initialize grid
        current_price = Decimal("45000")
        grid_orders = grid.initialize_grid(current_price)

        # Step 2: Check orders with risk manager
        approved_orders = []
        current_position = Decimal("0")

        for order in grid_orders[:3]:  # Try first 3 orders
            order_value = order.price * order.amount
            check = risk.check_trade(
                order_value,
                current_position,
                Decimal("10000") - current_position,
            )

            if check.allowed:
                approved_orders.append(order)
                current_position += order_value

        assert len(approved_orders) > 0

        # Step 3: Start DCA
        dca.execute_dca_step(current_price)

        # Step 4: Simulate price drop
        new_price = Decimal("42750")
        dca_actions = dca.update_price(new_price)

        # DCA should trigger
        assert dca_actions["dca_triggered"] is True

        # Step 5: Check if DCA is allowed by risk manager
        dca_value = Decimal("0.01") * new_price
        check = risk.check_trade(
            dca_value,
            current_position,
            Decimal("10000") - current_position,
        )

        # Should be allowed
        assert check.allowed is True

        # Step 6: Simulate profit - price recovers
        profit_price = Decimal("49500")

        # Check take profit
        tp_triggered = dca.check_take_profit(profit_price)
        assert tp_triggered is True

        # Step 7: Close position and update balance
        pnl = dca.close_position(profit_price)
        new_balance = Decimal("10000") + pnl
        risk.update_balance(new_balance)

        # Should have profit
        assert pnl > 0
        assert risk.current_balance > risk.initial_balance

        # Get final status from all modules
        grid_status = grid.get_grid_status()
        dca_status = dca.get_position_status()
        risk_status = risk.get_risk_status()

        assert grid_status["active_orders"] >= 0
        assert dca_status["has_position"] is False
        assert risk_status["is_halted"] is False

    def test_risk_manager_prevents_overtrading(self):
        """Test that risk manager prevents overtrading across all strategies"""
        grid = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=10,
            amount_per_grid=Decimal("500"),
            profit_per_grid=Decimal("0.01"),
        )

        risk = RiskManager(
            max_position_size=Decimal("2000"),
            min_order_size=Decimal("10"),
        )

        risk.initialize_balance(Decimal("5000"))

        # Try to place many grid orders
        grid_orders = grid.initialize_grid(Decimal("45000"))

        total_position = Decimal("0")
        approved_count = 0

        for order in grid_orders:
            order_value = order.price * order.amount
            check = risk.check_position_limit(total_position, order_value)

            if check.allowed:
                approved_count += 1
                total_position += order_value
            else:
                break

        # Should limit total position
        assert total_position <= risk.max_position_size
        assert approved_count < len(grid_orders)

        # Try DCA with remaining capacity
        dca_value = Decimal("500") * Decimal("45000")
        check = risk.check_position_limit(total_position, dca_value)

        # Should be rejected if it exceeds limit
        if total_position + dca_value > risk.max_position_size:
            assert check.allowed is False
