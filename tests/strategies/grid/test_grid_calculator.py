"""Tests for GridCalculator v2.0.

Tests arithmetic/geometric grid calculation, ATR-based dynamic adjustment,
optimal grid count, and full grid generation.
"""

from decimal import Decimal

import pytest

from bot.strategies.grid.grid_calculator import (
    GridCalculator,
    GridConfig,
    GridLevel,
    GridSpacing,
)


# =========================================================================
# GridConfig Tests
# =========================================================================


class TestGridConfig:
    def test_default_values(self):
        cfg = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=10,
        )
        assert cfg.spacing == GridSpacing.ARITHMETIC
        assert cfg.amount_per_grid == Decimal("100")
        assert cfg.profit_per_grid == Decimal("0.005")

    def test_validate_success(self):
        cfg = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=10,
        )
        cfg.validate()  # should not raise

    def test_validate_upper_le_lower(self):
        cfg = GridConfig(
            upper_price=Decimal("40000"),
            lower_price=Decimal("50000"),
            num_levels=10,
        )
        with pytest.raises(ValueError, match="upper_price must be greater"):
            cfg.validate()

    def test_validate_levels_too_few(self):
        cfg = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=1,
        )
        with pytest.raises(ValueError, match="num_levels must be at least 2"):
            cfg.validate()

    def test_validate_negative_amount(self):
        cfg = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=10,
            amount_per_grid=Decimal("-100"),
        )
        with pytest.raises(ValueError, match="amount_per_grid must be positive"):
            cfg.validate()

    def test_validate_negative_profit(self):
        cfg = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=10,
            profit_per_grid=Decimal("-0.01"),
        )
        with pytest.raises(ValueError, match="profit_per_grid must be non-negative"):
            cfg.validate()


# =========================================================================
# GridLevel Tests
# =========================================================================


class TestGridLevel:
    def test_to_dict(self):
        level = GridLevel(
            index=0, price=Decimal("45000"), side="buy", amount=Decimal("0.002")
        )
        d = level.to_dict()
        assert d["index"] == 0
        assert d["price"] == "45000"
        assert d["side"] == "buy"
        assert d["amount"] == "0.002"


# =========================================================================
# Arithmetic Grid Tests
# =========================================================================


class TestArithmeticGrid:
    def test_basic_5_levels(self):
        levels = GridCalculator.calculate_arithmetic_levels(
            Decimal("50000"), Decimal("40000"), 5
        )
        assert len(levels) == 5
        assert levels[0] == Decimal("40000.00")
        assert levels[-1] == Decimal("50000.00")

    def test_even_spacing(self):
        levels = GridCalculator.calculate_arithmetic_levels(
            Decimal("50000"), Decimal("40000"), 11
        )
        # Step should be 1000
        for i in range(1, len(levels)):
            step = levels[i] - levels[i - 1]
            assert step == Decimal("1000.00")

    def test_2_levels(self):
        levels = GridCalculator.calculate_arithmetic_levels(
            Decimal("100"), Decimal("50"), 2
        )
        assert levels == [Decimal("50.00"), Decimal("100.00")]

    def test_sorted_ascending(self):
        levels = GridCalculator.calculate_arithmetic_levels(
            Decimal("1000"), Decimal("100"), 20
        )
        for i in range(1, len(levels)):
            assert levels[i] > levels[i - 1]

    def test_invalid_levels_count(self):
        with pytest.raises(ValueError, match="num_levels must be at least 2"):
            GridCalculator.calculate_arithmetic_levels(
                Decimal("100"), Decimal("50"), 1
            )

    def test_invalid_price_order(self):
        with pytest.raises(ValueError, match="upper_price must be greater"):
            GridCalculator.calculate_arithmetic_levels(
                Decimal("50"), Decimal("100"), 5
            )


# =========================================================================
# Geometric Grid Tests
# =========================================================================


class TestGeometricGrid:
    def test_basic_5_levels(self):
        levels = GridCalculator.calculate_geometric_levels(
            Decimal("50000"), Decimal("40000"), 5
        )
        assert len(levels) == 5
        assert levels[0] == Decimal("40000.00")
        # Last level should be approximately 50000
        assert abs(levels[-1] - Decimal("50000")) < Decimal("1")

    def test_constant_ratio(self):
        levels = GridCalculator.calculate_geometric_levels(
            Decimal("10000"), Decimal("1000"), 10
        )
        pcts = GridCalculator.grid_spacing_pct(levels)
        # All percentage gaps should be approximately equal
        avg_pct = sum(pcts) / len(pcts)
        for pct in pcts:
            assert abs(pct - avg_pct) < Decimal("0.5")

    def test_denser_at_lower_prices(self):
        levels = GridCalculator.calculate_geometric_levels(
            Decimal("10000"), Decimal("1000"), 10
        )
        # Absolute gaps should increase as price increases
        gaps = [levels[i] - levels[i - 1] for i in range(1, len(levels))]
        for i in range(1, len(gaps)):
            assert gaps[i] > gaps[i - 1]

    def test_sorted_ascending(self):
        levels = GridCalculator.calculate_geometric_levels(
            Decimal("50000"), Decimal("10000"), 20
        )
        for i in range(1, len(levels)):
            assert levels[i] > levels[i - 1]

    def test_invalid_zero_lower(self):
        with pytest.raises(ValueError, match="lower_price must be positive"):
            GridCalculator.calculate_geometric_levels(
                Decimal("100"), Decimal("0"), 5
            )

    def test_invalid_negative_lower(self):
        with pytest.raises(ValueError, match="lower_price must be positive"):
            GridCalculator.calculate_geometric_levels(
                Decimal("100"), Decimal("-10"), 5
            )

    def test_invalid_levels_count(self):
        with pytest.raises(ValueError, match="num_levels must be at least 2"):
            GridCalculator.calculate_geometric_levels(
                Decimal("100"), Decimal("50"), 1
            )


# =========================================================================
# calculate_levels dispatcher Tests
# =========================================================================


class TestCalculateLevels:
    def test_arithmetic_dispatch(self):
        levels = GridCalculator.calculate_levels(
            Decimal("100"), Decimal("50"), 6, GridSpacing.ARITHMETIC
        )
        expected = GridCalculator.calculate_arithmetic_levels(
            Decimal("100"), Decimal("50"), 6
        )
        assert levels == expected

    def test_geometric_dispatch(self):
        levels = GridCalculator.calculate_levels(
            Decimal("100"), Decimal("50"), 6, GridSpacing.GEOMETRIC
        )
        expected = GridCalculator.calculate_geometric_levels(
            Decimal("100"), Decimal("50"), 6
        )
        assert levels == expected

    def test_default_is_arithmetic(self):
        levels = GridCalculator.calculate_levels(
            Decimal("100"), Decimal("50"), 6
        )
        expected = GridCalculator.calculate_arithmetic_levels(
            Decimal("100"), Decimal("50"), 6
        )
        assert levels == expected


# =========================================================================
# ATR Calculation Tests
# =========================================================================


class TestATRCalculation:
    @pytest.fixture
    def sample_price_data(self):
        """15 bars of sample OHLC data."""
        highs = [Decimal(str(x)) for x in [
            105, 108, 107, 110, 112, 109, 111, 115,
            113, 116, 114, 118, 117, 120, 119,
        ]]
        lows = [Decimal(str(x)) for x in [
            98, 100, 99, 103, 105, 102, 104, 108,
            106, 109, 107, 111, 110, 113, 112,
        ]]
        closes = [Decimal(str(x)) for x in [
            102, 106, 104, 108, 110, 106, 109, 113,
            110, 114, 112, 116, 114, 118, 116,
        ]]
        return highs, lows, closes

    def test_basic_atr(self, sample_price_data):
        highs, lows, closes = sample_price_data
        atr = GridCalculator.calculate_atr(highs, lows, closes, period=14)
        assert atr > 0
        assert isinstance(atr, Decimal)

    def test_atr_with_small_period(self, sample_price_data):
        highs, lows, closes = sample_price_data
        atr = GridCalculator.calculate_atr(highs, lows, closes, period=3)
        assert atr > 0

    def test_atr_minimum_data(self):
        # Minimum: 2 bars
        highs = [Decimal("110"), Decimal("115")]
        lows = [Decimal("100"), Decimal("105")]
        closes = [Decimal("105"), Decimal("110")]
        atr = GridCalculator.calculate_atr(highs, lows, closes, period=1)
        # TR for bar 1: max(115-105, |115-105|, |105-105|) = 10
        assert atr == Decimal("10.00")

    def test_atr_insufficient_data(self):
        with pytest.raises(ValueError, match="equal length >= 2"):
            GridCalculator.calculate_atr([Decimal("100")], [Decimal("90")], [Decimal("95")])

    def test_atr_mismatched_lengths(self):
        with pytest.raises(ValueError, match="equal length >= 2"):
            GridCalculator.calculate_atr(
                [Decimal("100"), Decimal("110")],
                [Decimal("90")],
                [Decimal("95"), Decimal("105")],
            )

    def test_atr_invalid_period(self):
        with pytest.raises(ValueError, match="period must be >= 1"):
            GridCalculator.calculate_atr(
                [Decimal("100"), Decimal("110")],
                [Decimal("90"), Decimal("100")],
                [Decimal("95"), Decimal("105")],
                period=0,
            )


# =========================================================================
# ATR-based Bounds Adjustment Tests
# =========================================================================


class TestATRBounds:
    def test_basic_bounds(self):
        upper, lower = GridCalculator.adjust_bounds_by_atr(
            Decimal("45000"), Decimal("500"), Decimal("3")
        )
        assert upper == Decimal("46500.00")
        assert lower == Decimal("43500.00")

    def test_bounds_symmetry(self):
        price = Decimal("10000")
        atr = Decimal("100")
        upper, lower = GridCalculator.adjust_bounds_by_atr(price, atr, Decimal("2"))
        # Symmetric around current price
        assert upper - price == price - lower

    def test_custom_multiplier(self):
        upper, lower = GridCalculator.adjust_bounds_by_atr(
            Decimal("1000"), Decimal("50"), Decimal("5")
        )
        assert upper == Decimal("1250.00")
        assert lower == Decimal("750.00")

    def test_invalid_atr(self):
        with pytest.raises(ValueError, match="atr must be positive"):
            GridCalculator.adjust_bounds_by_atr(
                Decimal("1000"), Decimal("0"), Decimal("3")
            )

    def test_invalid_multiplier(self):
        with pytest.raises(ValueError, match="atr_multiplier must be positive"):
            GridCalculator.adjust_bounds_by_atr(
                Decimal("1000"), Decimal("50"), Decimal("0")
            )

    def test_lower_bound_nonpositive(self):
        with pytest.raises(ValueError, match="non-positive"):
            GridCalculator.adjust_bounds_by_atr(
                Decimal("100"), Decimal("50"), Decimal("3")
            )


# =========================================================================
# Grid Order Generation Tests
# =========================================================================


class TestGridOrders:
    def test_buy_below_sell_above(self):
        levels = [Decimal("40000"), Decimal("42000"), Decimal("44000"),
                  Decimal("46000"), Decimal("48000"), Decimal("50000")]
        orders = GridCalculator.calculate_grid_orders(
            levels, Decimal("45000"), Decimal("100")
        )
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) == 3  # 40000, 42000, 44000
        assert len(sells) == 3  # 46000, 48000, 50000
        for b in buys:
            assert b.price < Decimal("45000")
        for s in sells:
            assert s.price >= Decimal("46000")

    def test_skip_current_price_level(self):
        levels = [Decimal("90"), Decimal("95"), Decimal("100"),
                  Decimal("105"), Decimal("110")]
        orders = GridCalculator.calculate_grid_orders(
            levels, Decimal("100"), Decimal("50")
        )
        prices = [o.price for o in orders]
        # Level at 100 should be skipped
        assert Decimal("100") not in prices
        assert len(orders) == 4

    def test_profit_margin_on_sells(self):
        levels = [Decimal("100"), Decimal("110")]
        orders = GridCalculator.calculate_grid_orders(
            levels, Decimal("90"), Decimal("100"), Decimal("0.01")
        )
        # Both levels above 90, should be sells with 1% profit margin
        assert len(orders) == 2
        assert orders[0].side == "sell"
        # 100 * 1.01 = 101
        assert orders[0].price == Decimal("101.00")

    def test_zero_profit_margin(self):
        levels = [Decimal("100"), Decimal("110")]
        orders = GridCalculator.calculate_grid_orders(
            levels, Decimal("90"), Decimal("50"), Decimal("0")
        )
        assert orders[0].price == Decimal("100.00")

    def test_amounts_in_base_currency(self):
        levels = [Decimal("50000")]
        orders = GridCalculator.calculate_grid_orders(
            levels, Decimal("60000"), Decimal("100")
        )
        # Buy at 50000, amount = 100/50000 = 0.002
        assert orders[0].amount == Decimal("0.002")

    def test_empty_when_all_at_current(self):
        levels = [Decimal("100")]
        orders = GridCalculator.calculate_grid_orders(
            levels, Decimal("100"), Decimal("50")
        )
        assert orders == []


# =========================================================================
# Optimal Grid Count Tests
# =========================================================================


class TestOptimalGridCount:
    def test_basic_calculation(self):
        count = GridCalculator.optimal_grid_count(
            Decimal("50000"), Decimal("40000"), Decimal("1000")
        )
        # (50000-40000)/1000 + 1 = 11
        assert count == 11

    def test_min_clamp(self):
        count = GridCalculator.optimal_grid_count(
            Decimal("50000"), Decimal("40000"), Decimal("10000"),
            min_levels=5,
        )
        # (50000-40000)/10000 + 1 = 2, clamped to 5
        assert count == 5

    def test_max_clamp(self):
        count = GridCalculator.optimal_grid_count(
            Decimal("50000"), Decimal("40000"), Decimal("10"),
            max_levels=50,
        )
        # (50000-40000)/10 + 1 = 1001, clamped to 50
        assert count == 50

    def test_invalid_atr(self):
        with pytest.raises(ValueError, match="atr must be positive"):
            GridCalculator.optimal_grid_count(
                Decimal("100"), Decimal("50"), Decimal("0")
            )

    def test_invalid_prices(self):
        with pytest.raises(ValueError, match="upper_price must be greater"):
            GridCalculator.optimal_grid_count(
                Decimal("50"), Decimal("100"), Decimal("10")
            )


# =========================================================================
# Full Grid Calculation Tests
# =========================================================================


class TestFullGrid:
    def test_arithmetic_full_grid(self):
        config = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=11,
            spacing=GridSpacing.ARITHMETIC,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.005"),
        )
        orders = GridCalculator.calculate_full_grid(config, Decimal("45000"))
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) == 5  # 40k, 41k, 42k, 43k, 44k
        assert len(sells) == 5  # 46k, 47k, 48k, 49k, 50k
        assert len(orders) == 10

    def test_geometric_full_grid(self):
        config = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=11,
            spacing=GridSpacing.GEOMETRIC,
            amount_per_grid=Decimal("100"),
        )
        orders = GridCalculator.calculate_full_grid(config, Decimal("45000"))
        assert len(orders) > 0
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) > 0
        assert len(sells) > 0

    def test_invalid_config_raises(self):
        config = GridConfig(
            upper_price=Decimal("40000"),
            lower_price=Decimal("50000"),
            num_levels=10,
        )
        with pytest.raises(ValueError):
            GridCalculator.calculate_full_grid(config, Decimal("45000"))


# =========================================================================
# ATR Grid Tests
# =========================================================================


class TestATRGrid:
    @pytest.fixture
    def price_data(self):
        """20 bars of price data for ATR calculation."""
        base = 45000
        highs, lows, closes = [], [], []
        for i in range(20):
            h = Decimal(str(base + 200 + (i % 5) * 50))
            l = Decimal(str(base - 200 - (i % 3) * 30))
            c = Decimal(str(base + (i % 7) * 20 - 60))
            highs.append(h)
            lows.append(l)
            closes.append(c)
        return highs, lows, closes

    def test_atr_grid_generates_orders(self, price_data):
        highs, lows, closes = price_data
        orders, meta = GridCalculator.calculate_atr_grid(
            current_price=Decimal("45000"),
            highs=highs,
            lows=lows,
            closes=closes,
        )
        assert len(orders) > 0
        assert "atr" in meta
        assert "upper_price" in meta
        assert "lower_price" in meta
        assert meta["total_orders"] == len(orders)

    def test_atr_grid_with_custom_levels(self, price_data):
        highs, lows, closes = price_data
        orders, meta = GridCalculator.calculate_atr_grid(
            current_price=Decimal("45000"),
            highs=highs,
            lows=lows,
            closes=closes,
            num_levels=10,
        )
        assert meta["num_levels"] == 10

    def test_atr_grid_geometric(self, price_data):
        highs, lows, closes = price_data
        orders, meta = GridCalculator.calculate_atr_grid(
            current_price=Decimal("45000"),
            highs=highs,
            lows=lows,
            closes=closes,
            spacing=GridSpacing.GEOMETRIC,
        )
        assert meta["spacing"] == "geometric"
        assert len(orders) > 0

    def test_atr_grid_metadata_completeness(self, price_data):
        highs, lows, closes = price_data
        _, meta = GridCalculator.calculate_atr_grid(
            current_price=Decimal("45000"),
            highs=highs,
            lows=lows,
            closes=closes,
        )
        expected_keys = {
            "atr", "atr_period", "atr_multiplier", "upper_price",
            "lower_price", "num_levels", "spacing", "total_orders",
            "buy_orders", "sell_orders",
        }
        assert set(meta.keys()) == expected_keys


# =========================================================================
# Utility Method Tests
# =========================================================================


class TestUtilities:
    def test_grid_spacing_pct_arithmetic(self):
        levels = GridCalculator.calculate_arithmetic_levels(
            Decimal("100"), Decimal("50"), 6
        )
        pcts = GridCalculator.grid_spacing_pct(levels)
        assert len(pcts) == 5
        # Arithmetic: pcts should decrease as price increases
        assert pcts[0] > pcts[-1]

    def test_grid_spacing_pct_geometric(self):
        levels = GridCalculator.calculate_geometric_levels(
            Decimal("10000"), Decimal("1000"), 10
        )
        pcts = GridCalculator.grid_spacing_pct(levels)
        # Geometric: all pcts should be approximately equal
        avg = sum(pcts) / len(pcts)
        for pct in pcts:
            assert abs(pct - avg) < Decimal("0.5")

    def test_grid_spacing_pct_empty(self):
        assert GridCalculator.grid_spacing_pct([]) == []
        assert GridCalculator.grid_spacing_pct([Decimal("100")]) == []

    def test_total_investment(self):
        orders = [
            GridLevel(0, Decimal("100"), "buy", Decimal("1.0")),
            GridLevel(1, Decimal("200"), "buy", Decimal("0.5")),
            GridLevel(2, Decimal("300"), "sell", Decimal("0.3")),
        ]
        total = GridCalculator.total_investment(orders)
        # Only buy orders: 100*1.0 + 200*0.5 = 200
        assert total == Decimal("200.00")

    def test_total_investment_no_buys(self):
        orders = [
            GridLevel(0, Decimal("300"), "sell", Decimal("0.3")),
        ]
        assert GridCalculator.total_investment(orders) == Decimal("0.00")
