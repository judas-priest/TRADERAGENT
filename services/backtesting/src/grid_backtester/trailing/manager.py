"""
TrailingGridManager — Dynamic grid shifting algorithm (Issue #4).

Monitors price vs grid boundaries and shifts the grid when price
moves beyond a threshold, keeping the grid centered around current price.

Supports:
- Fixed recentering: shift by half the grid spread
- ATR-based recentering: recalculate bounds from ATR
- Cooldown: minimum candles between shifts
"""

from decimal import Decimal
from typing import Any

from grid_backtester.core.calculator import GridCalculator, GridConfig, GridSpacing
from grid_backtester.logging import get_logger

logger = get_logger(__name__)


class TrailingGridManager:
    """
    Manages trailing grid shifts.

    Usage:
        manager = TrailingGridManager(
            shift_threshold_pct=Decimal("0.02"),
            recenter_mode="fixed",
            cooldown_candles=5,
        )

        # On each candle:
        new_config = manager.check_and_shift(
            current_price=price,
            current_upper=upper,
            current_lower=lower,
            grid_config=config,
        )
        if new_config:
            # Rebalance grid with new_config
            ...
    """

    def __init__(
        self,
        shift_threshold_pct: Decimal = Decimal("0.02"),
        recenter_mode: str = "fixed",
        cooldown_candles: int = 5,
        atr_period: int = 14,
        atr_multiplier: Decimal = Decimal("3.0"),
    ) -> None:
        self.shift_threshold_pct = shift_threshold_pct
        self.recenter_mode = recenter_mode
        self.cooldown_candles = cooldown_candles
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

        self._cooldown_remaining = 0
        self._shift_count = 0
        self._shift_history: list[dict[str, Any]] = []

    @property
    def shift_count(self) -> int:
        return self._shift_count

    @property
    def shift_history(self) -> list[dict[str, Any]]:
        return self._shift_history.copy()

    def tick(self) -> None:
        """Advance one candle — decrements cooldown."""
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1

    def check_and_shift(
        self,
        current_price: Decimal,
        current_upper: Decimal,
        current_lower: Decimal,
        grid_config: GridConfig,
        highs: list[Decimal] | None = None,
        lows: list[Decimal] | None = None,
        closes: list[Decimal] | None = None,
    ) -> GridConfig | None:
        """
        Check if grid should shift and return new config if so.

        Args:
            current_price: Current market price.
            current_upper: Current grid upper bound.
            current_lower: Current grid lower bound.
            grid_config: Current grid configuration.
            highs/lows/closes: Required for ATR mode recentering.

        Returns:
            New GridConfig if shift triggered, None otherwise.
        """
        if self._cooldown_remaining > 0:
            return None

        spread = current_upper - current_lower
        threshold = spread * self.shift_threshold_pct

        should_shift = False
        if current_price > current_upper + threshold:
            should_shift = True
        elif current_price < current_lower - threshold:
            should_shift = True

        if not should_shift:
            return None

        # Calculate new bounds
        if self.recenter_mode == "atr" and highs and lows and closes:
            new_upper, new_lower = self._recenter_atr(
                current_price, highs, lows, closes,
            )
        else:
            new_upper, new_lower = self._recenter_fixed(
                current_price, spread,
            )

        if new_lower <= 0:
            new_lower = Decimal("0.01")

        new_config = GridConfig(
            upper_price=new_upper,
            lower_price=new_lower,
            num_levels=grid_config.num_levels,
            spacing=grid_config.spacing,
            amount_per_grid=grid_config.amount_per_grid,
            profit_per_grid=grid_config.profit_per_grid,
        )

        self._cooldown_remaining = self.cooldown_candles
        self._shift_count += 1
        self._shift_history.append({
            "shift_number": self._shift_count,
            "price": float(current_price),
            "old_upper": float(current_upper),
            "old_lower": float(current_lower),
            "new_upper": float(new_upper),
            "new_lower": float(new_lower),
            "mode": self.recenter_mode,
        })

        logger.info(
            "Grid shift triggered",
            shift_number=self._shift_count,
            price=float(current_price),
            new_upper=float(new_upper),
            new_lower=float(new_lower),
            mode=self.recenter_mode,
        )

        return new_config

    def _recenter_fixed(
        self,
        current_price: Decimal,
        spread: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Recenter grid around current price with same spread."""
        new_upper = current_price + spread / 2
        new_lower = current_price - spread / 2
        return new_upper, new_lower

    def _recenter_atr(
        self,
        current_price: Decimal,
        highs: list[Decimal],
        lows: list[Decimal],
        closes: list[Decimal],
    ) -> tuple[Decimal, Decimal]:
        """Recenter grid using ATR-based bounds."""
        atr = GridCalculator.calculate_atr(
            highs, lows, closes, self.atr_period,
        )
        return GridCalculator.adjust_bounds_by_atr(
            current_price, atr, self.atr_multiplier,
        )

    def reset(self) -> None:
        """Reset trailing state."""
        self._cooldown_remaining = 0
        self._shift_count = 0
        self._shift_history.clear()
