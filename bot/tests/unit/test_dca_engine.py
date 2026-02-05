"""Tests for DCAEngine"""

from decimal import Decimal

import pytest

from bot.core.dca_engine import DCAEngine, DCAPosition


class TestDCAPosition:
    """Test DCAPosition functionality"""

    def test_init(self):
        """Test DCAPosition initialization"""
        position = DCAPosition(
            symbol="BTC/USDT",
            entry_price=Decimal("40000"),
            amount=Decimal("0.1"),
            step_number=0,
        )

        assert position.symbol == "BTC/USDT"
        assert position.entry_price == Decimal("40000")
        assert position.amount == Decimal("0.1")
        assert position.step_number == 0
        assert position.average_entry_price == Decimal("40000")

    def test_add_position(self):
        """Test adding to position"""
        position = DCAPosition(
            symbol="BTC/USDT",
            entry_price=Decimal("40000"),
            amount=Decimal("0.1"),
        )

        position.add_position(Decimal("38000"), Decimal("0.1"))

        assert position.amount == Decimal("0.2")
        assert position.step_number == 1
        # Average should be (40000*0.1 + 38000*0.1) / 0.2 = 39000
        assert position.average_entry_price == Decimal("39000")

    def test_get_pnl_profit(self):
        """Test PnL calculation with profit"""
        position = DCAPosition(
            symbol="BTC/USDT",
            entry_price=Decimal("40000"),
            amount=Decimal("0.1"),
        )

        pnl = position.get_pnl(Decimal("44000"))

        # (44000 - 40000) * 0.1 = 400
        assert pnl == Decimal("400")

    def test_get_pnl_loss(self):
        """Test PnL calculation with loss"""
        position = DCAPosition(
            symbol="BTC/USDT",
            entry_price=Decimal("40000"),
            amount=Decimal("0.1"),
        )

        pnl = position.get_pnl(Decimal("36000"))

        # (36000 - 40000) * 0.1 = -400
        assert pnl == Decimal("-400")

    def test_get_pnl_percentage(self):
        """Test PnL percentage calculation"""
        position = DCAPosition(
            symbol="BTC/USDT",
            entry_price=Decimal("40000"),
            amount=Decimal("0.1"),
        )

        pnl_pct = position.get_pnl_percentage(Decimal("44000"))

        # (44000 - 40000) / 40000 = 0.1 (10%)
        assert pnl_pct == Decimal("0.1")


class TestDCAEngine:
    """Test DCAEngine functionality"""

    def test_init_valid_params(self):
        """Test initialization with valid parameters"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        assert engine.symbol == "BTC/USDT"
        assert engine.trigger_percentage == Decimal("0.05")
        assert engine.amount_per_step == Decimal("100")
        assert engine.max_steps == 5
        assert engine.take_profit_percentage == Decimal("0.1")
        assert engine.position is None

    def test_init_invalid_trigger(self):
        """Test initialization with invalid trigger percentage"""
        with pytest.raises(ValueError, match="trigger_percentage must be"):
            DCAEngine(
                symbol="BTC/USDT",
                trigger_percentage=Decimal("1.5"),
                amount_per_step=Decimal("100"),
                max_steps=5,
                take_profit_percentage=Decimal("0.1"),
            )

    def test_init_invalid_amount(self):
        """Test initialization with invalid amount"""
        with pytest.raises(ValueError, match="amount_per_step must be positive"):
            DCAEngine(
                symbol="BTC/USDT",
                trigger_percentage=Decimal("0.05"),
                amount_per_step=Decimal("-100"),
                max_steps=5,
                take_profit_percentage=Decimal("0.1"),
            )

    def test_check_dca_trigger_no_position(self):
        """Test DCA trigger check with no position"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # Should trigger on first entry
        assert engine.check_dca_trigger(Decimal("40000")) is True

    def test_execute_dca_step_first_entry(self):
        """Test executing first DCA step"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        result = engine.execute_dca_step(Decimal("40000"))

        assert result is True
        assert engine.position is not None
        assert engine.position.entry_price == Decimal("40000")
        assert engine.position.step_number == 1
        assert engine.last_buy_price == Decimal("40000")

    def test_execute_dca_step_subsequent(self):
        """Test executing subsequent DCA steps"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # First entry
        engine.execute_dca_step(Decimal("40000"))

        # Price drops 5% to trigger next DCA
        engine.execute_dca_step(Decimal("38000"))

        assert engine.position is not None
        assert engine.position.step_number == 2
        # Average should be (40000*100 + 38000*100) / 200 = 39000
        assert engine.position.average_entry_price == Decimal("39000")

    def test_check_dca_trigger_max_steps_reached(self):
        """Test DCA trigger when max steps reached"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=2,
            take_profit_percentage=Decimal("0.1"),
        )

        # Execute max steps
        engine.execute_dca_step(Decimal("40000"))
        engine.execute_dca_step(Decimal("38000"))

        # Should not trigger another DCA
        assert engine.check_dca_trigger(Decimal("36000")) is False

    def test_check_take_profit(self):
        """Test take profit check"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # Open position at 40000
        engine.execute_dca_step(Decimal("40000"))

        # Price rises to trigger take profit (10% = 44000)
        assert engine.check_take_profit(Decimal("44000")) is True

    def test_check_take_profit_not_reached(self):
        """Test take profit when not reached"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # Open position at 40000
        engine.execute_dca_step(Decimal("40000"))

        # Price rises but not enough (5% = 42000)
        assert engine.check_take_profit(Decimal("42000")) is False

    def test_close_position(self):
        """Test closing position"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # Open position at 40000
        engine.execute_dca_step(Decimal("40000"))

        # Close at profit
        pnl = engine.close_position(Decimal("44000"))

        assert pnl > 0
        assert engine.position is None
        assert engine.last_buy_price is None
        assert engine.realized_profit == pnl

    def test_close_position_no_position(self):
        """Test closing position when none exists"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        pnl = engine.close_position(Decimal("40000"))

        assert pnl == Decimal("0")

    def test_get_target_sell_price(self):
        """Test target sell price calculation"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # No position
        assert engine.get_target_sell_price() is None

        # Open position at 40000
        engine.execute_dca_step(Decimal("40000"))

        target = engine.get_target_sell_price()
        # Should be 40000 * 1.1 = 44000
        assert target == Decimal("44000")

    def test_get_next_dca_trigger_price(self):
        """Test next DCA trigger price calculation"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # No position
        assert engine.get_next_dca_trigger_price() is None

        # Open position at 40000
        engine.execute_dca_step(Decimal("40000"))

        trigger = engine.get_next_dca_trigger_price()
        # Should be 40000 * 0.95 = 38000
        assert trigger == Decimal("38000")

    def test_update_price_dca_trigger(self):
        """Test update_price with DCA trigger"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # First entry should trigger
        actions = engine.update_price(Decimal("40000"))

        assert actions["dca_triggered"] is True
        assert actions["execute_dca"] is True
        assert actions["tp_triggered"] is False

    def test_update_price_take_profit(self):
        """Test update_price with take profit trigger"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # Open position
        engine.execute_dca_step(Decimal("40000"))

        # Price rises to trigger TP
        actions = engine.update_price(Decimal("44000"))

        assert actions["tp_triggered"] is True
        assert actions["take_profit"] is True
        assert actions["dca_triggered"] is False

    def test_get_position_status_no_position(self):
        """Test getting position status with no position"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        status = engine.get_position_status()

        assert status["has_position"] is False
        assert status["symbol"] == "BTC/USDT"
        assert status["total_dca_steps"] == 0

    def test_get_position_status_with_position(self):
        """Test getting position status with active position"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        engine.execute_dca_step(Decimal("40000"))

        status = engine.get_position_status()

        assert status["has_position"] is True
        assert status["average_entry_price"] == 40000.0
        assert status["position_amount"] == 100.0
        assert status["current_step"] == 1
        assert status["max_steps"] == 5

    def test_reset(self):
        """Test engine reset"""
        engine = DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.1"),
        )

        # Execute some steps
        engine.execute_dca_step(Decimal("40000"))
        engine.execute_dca_step(Decimal("38000"))

        # Reset
        engine.reset()

        assert engine.position is None
        assert engine.last_buy_price is None
        assert engine.total_dca_steps == 0
        assert engine.total_invested == Decimal("0")

    def test_dca_position_repr(self):
        """Test DCAPosition string representation"""
        position = DCAPosition(
            symbol="BTC/USDT",
            entry_price=Decimal("40000"),
            amount=Decimal("0.1"),
            step_number=2,
        )

        repr_str = repr(position)

        assert "DCAPosition" in repr_str
        assert "BTC/USDT" in repr_str
        assert "steps=2" in repr_str
