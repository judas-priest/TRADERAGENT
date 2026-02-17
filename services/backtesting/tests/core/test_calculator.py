"""Tests for GridCalculator."""

from decimal import Decimal

import pytest

from grid_backtester.core.calculator import (
    GridCalculator,
    GridConfig,
    GridLevel,
    GridSpacing,
)


class TestGridConfig:

    def test_valid_config(self):
        config = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=10,
        )
        config.validate()

    def test_invalid_bounds(self):
        config = GridConfig(
            upper_price=Decimal("40000"),
            lower_price=Decimal("50000"),
            num_levels=10,
        )
        with pytest.raises(ValueError):
            config.validate()

    def test_invalid_levels(self):
        config = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=1,
        )
        with pytest.raises(ValueError):
            config.validate()


class TestArithmeticGrid:

    def test_basic(self):
        levels = GridCalculator.calculate_arithmetic_levels(
            Decimal("50000"), Decimal("40000"), 6
        )
        assert len(levels) == 6
        assert levels[0] == Decimal("40000")
        assert levels[-1] == Decimal("50000")
        # Equal spacing
        step = levels[1] - levels[0]
        for i in range(1, len(levels)):
            assert abs(levels[i] - levels[i - 1] - step) < Decimal("0.1")


class TestGeometricGrid:

    def test_basic(self):
        levels = GridCalculator.calculate_geometric_levels(
            Decimal("50000"), Decimal("40000"), 6
        )
        assert len(levels) == 6
        assert levels[0] >= Decimal("39999")
        assert levels[-1] <= Decimal("50001")


class TestATR:

    def test_basic_atr(self):
        highs = [Decimal("105"), Decimal("110"), Decimal("108"), Decimal("112")]
        lows = [Decimal("95"), Decimal("100"), Decimal("98"), Decimal("102")]
        closes = [Decimal("100"), Decimal("105"), Decimal("103"), Decimal("110")]

        atr = GridCalculator.calculate_atr(highs, lows, closes, period=3)
        assert atr > 0

    def test_atr_bounds(self):
        upper, lower = GridCalculator.adjust_bounds_by_atr(
            Decimal("45000"), Decimal("500"), Decimal("3")
        )
        assert upper == Decimal("46500")
        assert lower == Decimal("43500")


class TestGridOrders:

    def test_buy_sell_sides(self):
        levels = GridCalculator.calculate_arithmetic_levels(
            Decimal("46000"), Decimal("44000"), 5
        )
        orders = GridCalculator.calculate_grid_orders(
            levels, Decimal("45000"), Decimal("100")
        )
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) > 0
        assert len(sells) > 0


class TestFullGrid:

    def test_full_grid_generation(self):
        config = GridConfig(
            upper_price=Decimal("46000"),
            lower_price=Decimal("44000"),
            num_levels=10,
            amount_per_grid=Decimal("100"),
        )
        orders = GridCalculator.calculate_full_grid(config, Decimal("45000"))
        assert len(orders) > 0
