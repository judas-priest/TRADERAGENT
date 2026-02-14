"""Tests for DCA Trailing Stop v2.0.

Tests highest price tracking, activation, stop price calculation,
trigger detection, snapshot persistence, and full lifecycle.
"""

from decimal import Decimal

import pytest

from bot.strategies.dca.dca_trailing_stop import (
    DCATrailingStop,
    TrailingStopConfig,
    TrailingStopResult,
    TrailingStopSnapshot,
    TrailingStopState,
    TrailingStopType,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def pct_config():
    return TrailingStopConfig(
        enabled=True,
        activation_pct=Decimal("1.5"),
        distance_pct=Decimal("0.8"),
        stop_type=TrailingStopType.PERCENTAGE,
    )


@pytest.fixture
def abs_config():
    return TrailingStopConfig(
        enabled=True,
        activation_pct=Decimal("1.5"),
        distance_abs=Decimal("25"),
        stop_type=TrailingStopType.ABSOLUTE,
    )


@pytest.fixture
def ts_pct(pct_config):
    return DCATrailingStop(pct_config)


@pytest.fixture
def ts_abs(abs_config):
    return DCATrailingStop(abs_config)


# =========================================================================
# Config Validation Tests
# =========================================================================


class TestTrailingStopConfig:
    def test_defaults(self):
        cfg = TrailingStopConfig()
        cfg.validate()

    def test_invalid_activation(self):
        cfg = TrailingStopConfig(activation_pct=Decimal("-1"))
        with pytest.raises(ValueError, match="activation_pct"):
            cfg.validate()

    def test_invalid_distance_pct(self):
        cfg = TrailingStopConfig(distance_pct=Decimal("0"))
        with pytest.raises(ValueError, match="distance_pct"):
            cfg.validate()

    def test_invalid_distance_abs(self):
        cfg = TrailingStopConfig(distance_abs=Decimal("-5"))
        with pytest.raises(ValueError, match="distance_abs"):
            cfg.validate()

    def test_get_distance_percentage(self, pct_config):
        assert pct_config.get_distance() == Decimal("0.8")

    def test_get_distance_absolute(self, abs_config):
        assert abs_config.get_distance() == Decimal("25")


# =========================================================================
# Stop Price Calculation Tests
# =========================================================================


class TestStopPriceCalculation:
    def test_percentage_stop(self, ts_pct):
        # highest=3500, distance=0.8% → 3500 * (1 - 0.008) = 3472
        stop = ts_pct.calculate_stop_price(Decimal("3500"))
        assert stop == Decimal("3472.00")

    def test_absolute_stop(self, ts_abs):
        # highest=3500, distance=25 → 3500 - 25 = 3475
        stop = ts_abs.calculate_stop_price(Decimal("3500"))
        assert stop == Decimal("3475")

    def test_stop_rises_with_highest(self, ts_pct):
        stop1 = ts_pct.calculate_stop_price(Decimal("3400"))
        stop2 = ts_pct.calculate_stop_price(Decimal("3500"))
        assert stop2 > stop1

    def test_small_price_percentage(self, ts_pct):
        stop = ts_pct.calculate_stop_price(Decimal("1.00"))
        assert stop == Decimal("0.99200")


# =========================================================================
# Activation Tests
# =========================================================================


class TestActivation:
    def test_inactive_below_threshold(self, ts_pct):
        result = ts_pct.evaluate(
            current_price=Decimal("3140"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3140"),
        )
        # 40/3100 = 1.29% < 1.5%
        assert result.state == TrailingStopState.INACTIVE
        assert result.should_exit is False

    def test_activates_above_threshold(self, ts_pct):
        result = ts_pct.evaluate(
            current_price=Decimal("3150"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3150"),
        )
        # 50/3100 = 1.61% > 1.5%
        assert result.state == TrailingStopState.ACTIVE
        assert result.should_exit is False

    def test_activation_exact_threshold(self, ts_pct):
        # 1.5% of 3100 = 46.5 → activation at 3146.5
        result = ts_pct.evaluate(
            current_price=Decimal("3146.50"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3146.50"),
        )
        assert result.state == TrailingStopState.ACTIVE

    def test_get_activation_price(self, ts_pct):
        price = ts_pct.get_activation_price(Decimal("3100"))
        assert price == Decimal("3146.500")

    def test_disabled_always_inactive(self):
        cfg = TrailingStopConfig(enabled=False)
        ts = DCATrailingStop(cfg)
        result = ts.evaluate(
            current_price=Decimal("5000"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("5000"),
        )
        assert result.state == TrailingStopState.INACTIVE
        assert result.should_exit is False


# =========================================================================
# Trigger Tests
# =========================================================================


class TestTrigger:
    def test_triggered_on_drop(self, ts_pct):
        # highest=3500, stop=3472, current=3470 → triggered
        result = ts_pct.evaluate(
            current_price=Decimal("3470"),
            average_entry=Decimal("3200"),
            highest_price=Decimal("3500"),
        )
        assert result.state == TrailingStopState.TRIGGERED
        assert result.should_exit is True
        assert result.stop_price == Decimal("3472.00")

    def test_not_triggered_above_stop(self, ts_pct):
        # highest=3500, stop=3472, current=3480 → active (not triggered)
        result = ts_pct.evaluate(
            current_price=Decimal("3480"),
            average_entry=Decimal("3200"),
            highest_price=Decimal("3500"),
        )
        assert result.state == TrailingStopState.ACTIVE
        assert result.should_exit is False

    def test_triggered_at_exact_stop(self, ts_pct):
        # exactly at stop price
        result = ts_pct.evaluate(
            current_price=Decimal("3472.00"),
            average_entry=Decimal("3200"),
            highest_price=Decimal("3500"),
        )
        assert result.state == TrailingStopState.TRIGGERED
        assert result.should_exit is True

    def test_triggered_absolute_type(self, ts_abs):
        # highest=3500, stop=3475, current=3474 → triggered
        result = ts_abs.evaluate(
            current_price=Decimal("3474"),
            average_entry=Decimal("3200"),
            highest_price=Decimal("3500"),
        )
        assert result.state == TrailingStopState.TRIGGERED
        assert result.should_exit is True

    def test_not_triggered_when_inactive(self, ts_pct):
        """Even if price drops below would-be stop, don't trigger if not activated."""
        result = ts_pct.evaluate(
            current_price=Decimal("3100"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3100"),
        )
        assert result.state == TrailingStopState.INACTIVE
        assert result.should_exit is False


# =========================================================================
# Highest Price Tracking Tests
# =========================================================================


class TestHighestPriceTracking:
    def test_update_new_high(self, ts_pct):
        new, updated = ts_pct.update_highest(Decimal("3400"), Decimal("3500"))
        assert new == Decimal("3500")
        assert updated is True

    def test_no_update_below(self, ts_pct):
        new, updated = ts_pct.update_highest(Decimal("3500"), Decimal("3400"))
        assert new == Decimal("3500")
        assert updated is False

    def test_no_update_equal(self, ts_pct):
        new, updated = ts_pct.update_highest(Decimal("3500"), Decimal("3500"))
        assert new == Decimal("3500")
        assert updated is False

    def test_highest_in_result(self, ts_pct):
        result = ts_pct.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3300"),
        )
        # current_price > highest_price is not the case here
        # highest stays at 3300
        assert result.highest_price == Decimal("3300")

    def test_highest_updated_in_result(self, ts_pct):
        result = ts_pct.evaluate(
            current_price=Decimal("3400"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3300"),
        )
        # current_price > highest → highest updated to 3400
        assert result.highest_price == Decimal("3400")

    def test_highest_not_reset_concept(self, ts_pct):
        """
        Demonstrate that highest is passed in, not stored internally.
        The caller (DCAPositionManager) is responsible for NOT resetting
        highest_price on safety order fills.
        """
        # First eval: highest=3400
        r1 = ts_pct.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3400"),
        )
        assert r1.highest_price == Decimal("3400")

        # Simulate safety order fill at 3050 — caller keeps highest=3400
        r2 = ts_pct.evaluate(
            current_price=Decimal("3050"),
            average_entry=Decimal("3075"),  # avg entry dropped
            highest_price=Decimal("3400"),  # NOT reset!
        )
        assert r2.highest_price == Decimal("3400")


# =========================================================================
# Snapshot Persistence Tests
# =========================================================================


class TestSnapshot:
    def test_snapshot_activation(self, ts_pct):
        snapshot = TrailingStopSnapshot()
        assert snapshot.is_activated is False

        ts_pct.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3200"),
            snapshot=snapshot,
        )
        assert snapshot.is_activated is True
        assert snapshot.activation_price == Decimal("3200")
        assert snapshot.activation_time is not None

    def test_snapshot_not_activated_below_threshold(self, ts_pct):
        snapshot = TrailingStopSnapshot()
        ts_pct.evaluate(
            current_price=Decimal("3140"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3140"),
            snapshot=snapshot,
        )
        assert snapshot.is_activated is False

    def test_snapshot_highest_updated(self, ts_pct):
        snapshot = TrailingStopSnapshot()
        ts_pct.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3200"),
            snapshot=snapshot,
        )
        assert snapshot.highest_price_since_entry == Decimal("3200")

        ts_pct.evaluate(
            current_price=Decimal("3300"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3300"),
            snapshot=snapshot,
        )
        assert snapshot.highest_price_since_entry == Decimal("3300")

    def test_snapshot_stop_price_updated(self, ts_pct):
        snapshot = TrailingStopSnapshot()
        ts_pct.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3200"),
            snapshot=snapshot,
        )
        assert snapshot.last_stop_price is not None

    def test_snapshot_activation_not_reset(self, ts_pct):
        """Once activated, stays activated even if price drops below threshold."""
        snapshot = TrailingStopSnapshot()
        # Activate
        ts_pct.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3200"),
            snapshot=snapshot,
        )
        activation_time = snapshot.activation_time
        assert snapshot.is_activated is True

        # Price drops but we still pass highest
        ts_pct.evaluate(
            current_price=Decimal("3150"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3200"),
            snapshot=snapshot,
        )
        # Activation time should not change
        assert snapshot.activation_time == activation_time


# =========================================================================
# Edge Cases
# =========================================================================


class TestEdgeCases:
    def test_zero_average_entry(self, ts_pct):
        result = ts_pct.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("0"),
            highest_price=Decimal("3200"),
        )
        assert result.state == TrailingStopState.INACTIVE

    def test_negative_profit(self, ts_pct):
        result = ts_pct.evaluate(
            current_price=Decimal("3000"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3100"),
        )
        assert result.state == TrailingStopState.INACTIVE

    def test_large_profit(self, ts_pct):
        result = ts_pct.evaluate(
            current_price=Decimal("5000"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("5000"),
        )
        assert result.state == TrailingStopState.ACTIVE
        assert result.current_profit_pct > Decimal("50")

    def test_default_config(self):
        ts = DCATrailingStop()
        result = ts.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3200"),
        )
        assert isinstance(result, TrailingStopResult)

    def test_result_to_dict(self, ts_pct):
        result = ts_pct.evaluate(
            current_price=Decimal("3200"),
            average_entry=Decimal("3100"),
            highest_price=Decimal("3200"),
        )
        d = result.to_dict()
        assert "state" in d
        assert "should_exit" in d
        assert "stop_price" in d

    def test_statistics(self, ts_pct):
        stats = ts_pct.get_statistics()
        assert stats["enabled"] is True
        assert stats["stop_type"] == "percentage"
        assert stats["activation_pct"] == "1.5"

    def test_enabled_property(self, ts_pct):
        assert ts_pct.enabled is True

    def test_disabled_property(self):
        ts = DCATrailingStop(TrailingStopConfig(enabled=False))
        assert ts.enabled is False


# =========================================================================
# Full Lifecycle Integration Test
# =========================================================================


class TestFullLifecycle:
    def test_complete_trailing_stop_cycle(self, ts_pct):
        """
        Simulate: entry → price rises → activation → new highs →
        price drops → trailing triggered → exit.
        """
        avg_entry = Decimal("3100")
        snapshot = TrailingStopSnapshot()

        # Step 1: Price barely up — inactive
        r = ts_pct.evaluate(Decimal("3130"), avg_entry, Decimal("3130"), snapshot)
        assert r.state == TrailingStopState.INACTIVE

        # Step 2: Price rises past activation (1.5% = 3146.50)
        r = ts_pct.evaluate(Decimal("3200"), avg_entry, Decimal("3200"), snapshot)
        assert r.state == TrailingStopState.ACTIVE
        assert snapshot.is_activated is True

        # Step 3: Price keeps rising
        r = ts_pct.evaluate(Decimal("3400"), avg_entry, Decimal("3400"), snapshot)
        assert r.state == TrailingStopState.ACTIVE
        assert snapshot.highest_price_since_entry == Decimal("3400")

        # Step 4: New all-time high
        r = ts_pct.evaluate(Decimal("3500"), avg_entry, Decimal("3500"), snapshot)
        assert r.state == TrailingStopState.ACTIVE
        assert r.stop_price == Decimal("3472.00")  # 3500 * (1-0.008)

        # Step 5: Price drops but above stop
        r = ts_pct.evaluate(Decimal("3480"), avg_entry, Decimal("3500"), snapshot)
        assert r.state == TrailingStopState.ACTIVE
        assert r.should_exit is False

        # Step 6: Price drops to stop — TRIGGERED
        r = ts_pct.evaluate(Decimal("3470"), avg_entry, Decimal("3500"), snapshot)
        assert r.state == TrailingStopState.TRIGGERED
        assert r.should_exit is True
        assert r.stop_price == Decimal("3472.00")

    def test_safety_order_does_not_reset_highest(self, ts_pct):
        """
        Key behavior: safety order fills at lower price do NOT reset highest.
        """
        avg_entry = Decimal("3100")
        snapshot = TrailingStopSnapshot()

        # Price rises to 3400 — activate trailing
        ts_pct.evaluate(Decimal("3400"), avg_entry, Decimal("3400"), snapshot)
        assert snapshot.highest_price_since_entry == Decimal("3400")

        # Safety order fills at 3050 — average entry drops
        new_avg = Decimal("3075")  # Recalculated after SO

        # Caller keeps highest at 3400 (NOT reset)
        r = ts_pct.evaluate(Decimal("3050"), new_avg, Decimal("3400"), snapshot)
        assert snapshot.highest_price_since_entry == Decimal("3400")

        # Price recovers above stop (3400 * 0.992 = 3372.80)
        r = ts_pct.evaluate(Decimal("3380"), new_avg, Decimal("3400"), snapshot)
        assert r.state == TrailingStopState.ACTIVE
        # Stop is still based on 3400 highest
        assert r.stop_price == Decimal("3372.80")  # 3400 * 0.992

    def test_absolute_trailing_full_cycle(self, ts_abs):
        """Full cycle with absolute distance ($25)."""
        avg_entry = Decimal("3100")

        # Activate
        r = ts_abs.evaluate(Decimal("3200"), avg_entry, Decimal("3200"))
        assert r.state == TrailingStopState.ACTIVE

        # New high
        r = ts_abs.evaluate(Decimal("3500"), avg_entry, Decimal("3500"))
        assert r.stop_price == Decimal("3475")

        # Triggered
        r = ts_abs.evaluate(Decimal("3474"), avg_entry, Decimal("3500"))
        assert r.state == TrailingStopState.TRIGGERED
        assert r.should_exit is True
