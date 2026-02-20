"""
DCA Trailing Stop — v2.0.

Dynamic trailing stop-loss that follows price highs to protect profit:
- Tracks highest_price_since_entry (never reset on safety orders)
- Activates only after minimum profit threshold is reached
- Calculates stop price as percentage or absolute distance from highest
- Programmatic execution (not exchange-level orders)

Key principle: The trailing stop highest price is NEVER reset when
safety orders fill, preserving accumulated profit protection.

Usage:
    config = TrailingStopConfig(activation_pct=Decimal("1.5"), ...)
    ts = DCATrailingStop(config)
    result = ts.evaluate(
        current_price=Decimal("3500"),
        average_entry=Decimal("3200"),
        highest_price=Decimal("3500"),
    )
    if result.should_exit:
        # Close position at market
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

# =============================================================================
# Enums
# =============================================================================


class TrailingStopType(str, Enum):
    """Type of trailing stop distance calculation."""

    PERCENTAGE = "percentage"  # Stop at highest * (1 - distance/100)
    ABSOLUTE = "absolute"  # Stop at highest - distance


class TrailingStopState(str, Enum):
    """Current state of the trailing stop."""

    INACTIVE = "inactive"  # Profit below activation threshold
    ACTIVE = "active"  # Trailing is active, tracking highest
    TRIGGERED = "triggered"  # Stop price hit, exit signal


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class TrailingStopResult:
    """Result of a trailing stop evaluation."""

    state: TrailingStopState
    should_exit: bool
    stop_price: Decimal | None = None
    current_profit_pct: Decimal = Decimal("0")
    highest_price: Decimal = Decimal("0")
    distance_to_stop_pct: Decimal | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "should_exit": self.should_exit,
            "stop_price": str(self.stop_price) if self.stop_price else None,
            "current_profit_pct": str(self.current_profit_pct),
            "highest_price": str(self.highest_price),
            "distance_to_stop_pct": (
                str(self.distance_to_stop_pct) if self.distance_to_stop_pct else None
            ),
            "reason": self.reason,
        }


@dataclass
class TrailingStopSnapshot:
    """
    Persistent state for a deal's trailing stop.

    Store this in the deal record for persistence across restarts.
    """

    highest_price_since_entry: Decimal = Decimal("0")
    is_activated: bool = False
    activation_price: Decimal | None = None
    activation_time: datetime | None = None
    last_stop_price: Decimal | None = None


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class TrailingStopConfig:
    """
    Trailing stop configuration.

    Attributes:
        enabled: Whether trailing stop is active.
        activation_pct: Minimum profit % to activate trailing.
        distance_pct: Distance from highest for percentage type.
        distance_abs: Distance from highest for absolute type.
        stop_type: Percentage or absolute calculation.
    """

    enabled: bool = True
    activation_pct: Decimal = Decimal("1.5")  # Activate at 1.5% profit
    distance_pct: Decimal = Decimal("0.8")  # 0.8% from highest
    distance_abs: Decimal = Decimal("25")  # $25 from highest (for absolute type)
    stop_type: TrailingStopType = TrailingStopType.PERCENTAGE

    def validate(self) -> None:
        """Validate configuration."""
        if self.activation_pct < 0:
            raise ValueError("activation_pct must be >= 0")
        if self.distance_pct <= 0:
            raise ValueError("distance_pct must be positive")
        if self.distance_abs <= 0:
            raise ValueError("distance_abs must be positive")

    def get_distance(self) -> Decimal:
        """Get the configured distance based on stop type."""
        if self.stop_type == TrailingStopType.PERCENTAGE:
            return self.distance_pct
        return self.distance_abs


# =============================================================================
# DCA Trailing Stop
# =============================================================================


class DCATrailingStop:
    """
    Programmatic trailing stop for DCA deals.

    Evaluates current market price against the highest price since entry
    to determine whether to exit the position.

    The trailing stop lifecycle:
    1. INACTIVE: Profit is below activation threshold
    2. ACTIVE: Profit exceeded threshold, tracking highest price
    3. TRIGGERED: Price dropped below stop price, exit signal

    Important behaviors:
    - highest_price is NEVER reset on safety order fills
    - Stop price calculation is dynamic (recalculated each evaluation)
    - Both percentage and absolute distance modes are supported
    """

    def __init__(self, config: TrailingStopConfig | None = None):
        self._config = config or TrailingStopConfig()
        if self._config.enabled:
            self._config.validate()

    @property
    def config(self) -> TrailingStopConfig:
        return self._config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    # -----------------------------------------------------------------
    # Core Evaluation
    # -----------------------------------------------------------------

    def evaluate(
        self,
        current_price: Decimal,
        average_entry: Decimal,
        highest_price: Decimal,
        snapshot: TrailingStopSnapshot | None = None,
    ) -> TrailingStopResult:
        """
        Evaluate trailing stop condition.

        Args:
            current_price: Current market price.
            average_entry: Current average entry price (after all SOs).
            highest_price: Highest price since entry (caller must track).
            snapshot: Optional persistent state for activation tracking.

        Returns:
            TrailingStopResult with exit decision.
        """
        if not self._config.enabled:
            return TrailingStopResult(
                state=TrailingStopState.INACTIVE,
                should_exit=False,
                reason="Trailing stop disabled",
            )

        if average_entry <= 0:
            return TrailingStopResult(
                state=TrailingStopState.INACTIVE,
                should_exit=False,
                reason="Invalid average entry",
            )

        # Update highest price
        new_highest = max(highest_price, current_price)

        # Calculate current profit
        profit_pct = ((current_price - average_entry) / average_entry) * 100

        # Check activation
        if profit_pct < self._config.activation_pct:
            return TrailingStopResult(
                state=TrailingStopState.INACTIVE,
                should_exit=False,
                current_profit_pct=profit_pct,
                highest_price=new_highest,
                reason=(
                    f"Profit {profit_pct:.2f}% below activation "
                    f"({self._config.activation_pct}%)"
                ),
            )

        # Trailing is active — calculate stop price
        stop_price = self.calculate_stop_price(new_highest)

        # Update snapshot if provided
        if snapshot is not None and not snapshot.is_activated:
            snapshot.is_activated = True
            snapshot.activation_price = current_price
            snapshot.activation_time = datetime.now(timezone.utc)
        if snapshot is not None:
            snapshot.highest_price_since_entry = new_highest
            snapshot.last_stop_price = stop_price

        # Check if stop is triggered
        if current_price <= stop_price:
            return TrailingStopResult(
                state=TrailingStopState.TRIGGERED,
                should_exit=True,
                stop_price=stop_price,
                current_profit_pct=profit_pct,
                highest_price=new_highest,
                distance_to_stop_pct=Decimal("0"),
                reason=(
                    f"Trailing stop triggered: price {current_price} "
                    f"<= stop {stop_price} (highest: {new_highest})"
                ),
            )

        # Active but not triggered
        distance_to_stop = (
            ((current_price - stop_price) / current_price) * 100
            if current_price > 0
            else Decimal("0")
        )

        return TrailingStopResult(
            state=TrailingStopState.ACTIVE,
            should_exit=False,
            stop_price=stop_price,
            current_profit_pct=profit_pct,
            highest_price=new_highest,
            distance_to_stop_pct=distance_to_stop,
            reason=(f"Trailing active: stop={stop_price}, " f"distance={distance_to_stop:.2f}%"),
        )

    # -----------------------------------------------------------------
    # Stop Price Calculation
    # -----------------------------------------------------------------

    def calculate_stop_price(self, highest_price: Decimal) -> Decimal:
        """
        Calculate the current stop price based on highest price.

        For PERCENTAGE type: highest * (1 - distance/100)
        For ABSOLUTE type: highest - distance
        """
        cfg = self._config

        if cfg.stop_type == TrailingStopType.PERCENTAGE:
            return highest_price * (1 - cfg.distance_pct / 100)
        else:
            return highest_price - cfg.distance_abs

    # -----------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------

    def update_highest(
        self, current_highest: Decimal, current_price: Decimal
    ) -> tuple[Decimal, bool]:
        """
        Update highest price. Returns (new_highest, was_updated).

        This should be called on every price update. The highest
        is NEVER reduced, only increased.
        """
        if current_price > current_highest:
            return current_price, True
        return current_highest, False

    def get_activation_price(self, average_entry: Decimal) -> Decimal:
        """Calculate the price at which trailing stop activates."""
        return average_entry * (1 + self._config.activation_pct / 100)

    def get_statistics(self) -> dict[str, Any]:
        """Return config summary."""
        cfg = self._config
        return {
            "enabled": cfg.enabled,
            "stop_type": cfg.stop_type.value,
            "activation_pct": str(cfg.activation_pct),
            "distance": (
                str(cfg.distance_pct) + "%"
                if cfg.stop_type == TrailingStopType.PERCENTAGE
                else str(cfg.distance_abs)
            ),
        }
