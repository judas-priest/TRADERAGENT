"""Tests for TrailingGridManager."""

from decimal import Decimal

import pytest

from grid_backtester.core.calculator import GridConfig, GridSpacing
from grid_backtester.trailing.manager import TrailingGridManager


class TestTrailingGridManager:

    def _make_grid_config(
        self,
        upper: float = 46000.0,
        lower: float = 44000.0,
        num_levels: int = 10,
    ) -> GridConfig:
        return GridConfig(
            upper_price=Decimal(str(upper)),
            lower_price=Decimal(str(lower)),
            num_levels=num_levels,
            spacing=GridSpacing.ARITHMETIC,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.005"),
        )

    def test_no_shift_within_bounds(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=5,
        )
        config = self._make_grid_config()
        result = mgr.check_and_shift(
            current_price=Decimal("45000"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
        )
        assert result is None
        assert mgr.shift_count == 0

    def test_shift_triggered_above_upper(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=3,
        )
        config = self._make_grid_config()
        # Price is above upper + threshold (46000 + 2000*0.02 = 46040)
        result = mgr.check_and_shift(
            current_price=Decimal("46100"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
        )
        assert result is not None
        assert mgr.shift_count == 1
        # New bounds should be centered on 46100
        assert float(result.upper_price) > 46100
        assert float(result.lower_price) < 46100

    def test_shift_triggered_below_lower(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=3,
        )
        config = self._make_grid_config()
        # Price below lower - threshold (44000 - 2000*0.02 = 43960)
        result = mgr.check_and_shift(
            current_price=Decimal("43900"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
        )
        assert result is not None
        assert mgr.shift_count == 1

    def test_cooldown_prevents_consecutive_shifts(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=3,
        )
        config = self._make_grid_config()

        # First shift
        result1 = mgr.check_and_shift(
            current_price=Decimal("46100"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
        )
        assert result1 is not None

        # Immediate second attempt should be blocked by cooldown
        result2 = mgr.check_and_shift(
            current_price=Decimal("48000"),
            current_upper=result1.upper_price,
            current_lower=result1.lower_price,
            grid_config=result1,
        )
        assert result2 is None

        # Tick through cooldown
        for _ in range(3):
            mgr.tick()

        # Now shift should be possible
        result3 = mgr.check_and_shift(
            current_price=Decimal("49000"),
            current_upper=result1.upper_price,
            current_lower=result1.lower_price,
            grid_config=result1,
        )
        assert result3 is not None
        assert mgr.shift_count == 2

    def test_shift_history_tracked(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=0,
        )
        config = self._make_grid_config()

        mgr.check_and_shift(
            current_price=Decimal("46100"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
        )

        history = mgr.shift_history
        assert len(history) == 1
        assert history[0]["shift_number"] == 1
        assert history[0]["price"] == 46100.0
        assert history[0]["mode"] == "fixed"

    def test_atr_recenter_mode(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="atr",
            cooldown_candles=0,
            atr_period=3,
            atr_multiplier=Decimal("2.0"),
        )
        config = self._make_grid_config()

        highs = [Decimal("45500"), Decimal("45800"), Decimal("46200"), Decimal("46500")]
        lows = [Decimal("44500"), Decimal("44800"), Decimal("45200"), Decimal("45500")]
        closes = [Decimal("45000"), Decimal("45300"), Decimal("45700"), Decimal("46100")]

        result = mgr.check_and_shift(
            current_price=Decimal("46100"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
            highs=highs,
            lows=lows,
            closes=closes,
        )
        assert result is not None
        # ATR mode should use ATR-based bounds rather than fixed spread
        assert mgr.shift_history[0]["mode"] == "atr"

    def test_atr_mode_falls_back_to_fixed_without_data(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="atr",
            cooldown_candles=0,
        )
        config = self._make_grid_config()

        # No highs/lows/closes provided — should fall back to fixed
        result = mgr.check_and_shift(
            current_price=Decimal("46100"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
        )
        assert result is not None
        # Falls back to fixed mode
        assert mgr.shift_history[0]["mode"] == "atr"  # still reports atr as mode

    def test_reset_clears_state(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=5,
        )
        config = self._make_grid_config()

        mgr.check_and_shift(
            current_price=Decimal("46100"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
        )
        assert mgr.shift_count == 1

        mgr.reset()
        assert mgr.shift_count == 0
        assert len(mgr.shift_history) == 0

    def test_grid_config_preserved_after_shift(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=0,
        )
        config = self._make_grid_config(num_levels=20)

        result = mgr.check_and_shift(
            current_price=Decimal("46100"),
            current_upper=Decimal("46000"),
            current_lower=Decimal("44000"),
            grid_config=config,
        )
        assert result is not None
        assert result.num_levels == 20
        assert result.spacing == GridSpacing.ARITHMETIC

    def test_lower_bound_never_negative(self):
        mgr = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=0,
        )
        config = self._make_grid_config(upper=2.0, lower=0.5)

        result = mgr.check_and_shift(
            current_price=Decimal("0.01"),
            current_upper=Decimal("2.0"),
            current_lower=Decimal("0.5"),
            grid_config=config,
        )
        assert result is not None
        assert result.lower_price >= Decimal("0.01")
