"""
GridRiskManager — Risk management for grid trading strategy.

Responsibilities:
- Position size limits (per-grid and total exposure)
- Grid-wide stop-loss
- Trend detection for grid deactivation
- Drawdown monitoring
- Exposure and PnL thresholds
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums & Configuration
# =============================================================================


class GridRiskAction(str, Enum):
    """Actions the risk manager can recommend."""

    CONTINUE = "continue"
    PAUSE = "pause"  # pause new orders, keep existing
    REDUCE = "reduce"  # cancel some orders
    STOP_LOSS = "stop_loss"  # close all, grid-wide stop
    DEACTIVATE = "deactivate"  # deactivate grid (trending market)


class TrendState(str, Enum):
    """Market trend classification for grid suitability."""

    RANGING = "ranging"  # ideal for grid
    MILD_TREND = "mild_trend"  # acceptable
    STRONG_TREND = "strong_trend"  # should deactivate


@dataclass
class GridRiskConfig:
    """Configuration for grid risk management."""

    # Position size limits
    max_position_size: Decimal = Decimal("1000")  # max quote per single order
    max_total_exposure: Decimal = Decimal("10000")  # max total quote across all orders
    max_open_orders: int = 50  # max simultaneous open orders

    # Stop-loss
    grid_stop_loss_pct: Decimal = Decimal("0.05")  # 5% grid-wide SL
    max_unrealized_loss: Decimal = Decimal("500")  # absolute max loss

    # Drawdown limits
    max_drawdown_pct: Decimal = Decimal("0.10")  # 10% max drawdown from peak
    max_consecutive_losses: int = 5

    # Trend detection thresholds
    trend_atr_multiplier: Decimal = Decimal("2.0")  # price move > N*ATR = trending
    trend_adx_threshold: float = 25.0  # ADX > threshold = trending

    # Balance protection
    min_balance_pct: Decimal = Decimal("0.20")  # keep 20% of balance free

    def validate(self) -> None:
        if self.max_position_size <= 0:
            raise ValueError("max_position_size must be positive")
        if self.max_total_exposure <= 0:
            raise ValueError("max_total_exposure must be positive")
        if self.max_open_orders < 1:
            raise ValueError("max_open_orders must be at least 1")
        if self.grid_stop_loss_pct <= 0:
            raise ValueError("grid_stop_loss_pct must be positive")
        if self.max_drawdown_pct <= 0 or self.max_drawdown_pct > 1:
            raise ValueError("max_drawdown_pct must be between 0 and 1")
        if self.min_balance_pct < 0 or self.min_balance_pct > 1:
            raise ValueError("min_balance_pct must be between 0 and 1")


# =============================================================================
# Risk Check Result
# =============================================================================


@dataclass
class RiskCheckResult:
    """Result of a risk evaluation."""

    action: GridRiskAction
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return self.action == GridRiskAction.CONTINUE

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "is_safe": self.is_safe,
            "reasons": self.reasons,
            "warnings": self.warnings,
        }


# =============================================================================
# Grid Risk Manager
# =============================================================================


class GridRiskManager:
    """
    Manages risk for grid trading strategy.

    Evaluates position sizes, exposure, stop-loss triggers,
    drawdown, and market conditions to determine if grid should continue.
    """

    def __init__(self, config: GridRiskConfig | None = None) -> None:
        self._config = config or GridRiskConfig()
        self._config.validate()

        # State tracking
        self._peak_equity = Decimal("0")
        self._consecutive_losses = 0
        self._grid_entry_price = Decimal("0")  # price when grid was activated
        self._total_realized_pnl = Decimal("0")

        logger.info("GridRiskManager initialized")

    @property
    def config(self) -> GridRiskConfig:
        return self._config

    # =================================================================
    # Position Size Validation
    # =================================================================

    def validate_order_size(
        self,
        order_quote_value: Decimal,
        current_total_exposure: Decimal,
        current_open_orders: int,
    ) -> RiskCheckResult:
        """
        Validate whether a new order can be placed.

        Args:
            order_quote_value: Quote currency value of the new order.
            current_total_exposure: Current total exposure across all orders.
            current_open_orders: Current number of open orders.

        Returns:
            RiskCheckResult with action and reasons.
        """
        result = RiskCheckResult(action=GridRiskAction.CONTINUE)

        if order_quote_value > self._config.max_position_size:
            result.action = GridRiskAction.PAUSE
            result.reasons.append(
                f"Order size {order_quote_value} exceeds max {self._config.max_position_size}"
            )

        new_exposure = current_total_exposure + order_quote_value
        if new_exposure > self._config.max_total_exposure:
            result.action = GridRiskAction.PAUSE
            result.reasons.append(
                f"Total exposure {new_exposure} would exceed max {self._config.max_total_exposure}"
            )

        if current_open_orders >= self._config.max_open_orders:
            result.action = GridRiskAction.PAUSE
            result.reasons.append(
                f"Open orders {current_open_orders} at max {self._config.max_open_orders}"
            )

        if not result.reasons:
            # Add warnings for approaching limits
            exposure_pct = float(new_exposure / self._config.max_total_exposure)
            if exposure_pct > 0.8:
                result.warnings.append(
                    f"Exposure at {exposure_pct:.0%} of max"
                )
            orders_pct = current_open_orders / self._config.max_open_orders
            if orders_pct > 0.8:
                result.warnings.append(
                    f"Open orders at {orders_pct:.0%} of max"
                )

        return result

    # =================================================================
    # Stop-Loss Check
    # =================================================================

    def check_grid_stop_loss(
        self,
        current_price: Decimal,
        grid_entry_price: Decimal | None = None,
        unrealized_pnl: Decimal = Decimal("0"),
    ) -> RiskCheckResult:
        """
        Check if grid-wide stop-loss should trigger.

        Triggers on:
        1. Price moved beyond grid_stop_loss_pct from entry
        2. Unrealized loss exceeds max_unrealized_loss

        Args:
            current_price: Current market price.
            grid_entry_price: Price when grid was started (optional, uses stored).
            unrealized_pnl: Current unrealized PnL.

        Returns:
            RiskCheckResult.
        """
        entry = grid_entry_price or self._grid_entry_price
        result = RiskCheckResult(action=GridRiskAction.CONTINUE)

        if entry > 0:
            price_change_pct = abs(current_price - entry) / entry
            if price_change_pct >= self._config.grid_stop_loss_pct:
                result.action = GridRiskAction.STOP_LOSS
                result.reasons.append(
                    f"Price moved {float(price_change_pct):.2%} from entry "
                    f"(limit: {float(self._config.grid_stop_loss_pct):.2%})"
                )

        if unrealized_pnl < 0 and abs(unrealized_pnl) >= self._config.max_unrealized_loss:
            result.action = GridRiskAction.STOP_LOSS
            result.reasons.append(
                f"Unrealized loss {unrealized_pnl} exceeds max {self._config.max_unrealized_loss}"
            )

        return result

    # =================================================================
    # Drawdown Check
    # =================================================================

    def check_drawdown(
        self, current_equity: Decimal
    ) -> RiskCheckResult:
        """
        Check if drawdown from peak equity exceeds the limit.

        Args:
            current_equity: Current account equity.

        Returns:
            RiskCheckResult.
        """
        # Update peak
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        result = RiskCheckResult(action=GridRiskAction.CONTINUE)

        if self._peak_equity > 0:
            drawdown = (self._peak_equity - current_equity) / self._peak_equity
            if drawdown >= self._config.max_drawdown_pct:
                result.action = GridRiskAction.STOP_LOSS
                result.reasons.append(
                    f"Drawdown {float(drawdown):.2%} exceeds max "
                    f"{float(self._config.max_drawdown_pct):.2%}"
                )
            elif drawdown >= self._config.max_drawdown_pct * Decimal("0.7"):
                result.warnings.append(
                    f"Drawdown {float(drawdown):.2%} approaching limit"
                )

        return result

    # =================================================================
    # Consecutive Loss Check
    # =================================================================

    def record_trade_result(self, profit: Decimal) -> None:
        """Record a trade result for consecutive loss tracking."""
        self._total_realized_pnl += profit
        if profit < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def check_consecutive_losses(self) -> RiskCheckResult:
        """Check if consecutive losses exceed the limit."""
        result = RiskCheckResult(action=GridRiskAction.CONTINUE)
        if self._consecutive_losses >= self._config.max_consecutive_losses:
            result.action = GridRiskAction.PAUSE
            result.reasons.append(
                f"{self._consecutive_losses} consecutive losses "
                f"(max: {self._config.max_consecutive_losses})"
            )
        return result

    # =================================================================
    # Trend Detection (Grid Deactivation)
    # =================================================================

    def check_trend_suitability(
        self,
        atr: Decimal,
        price_move: Decimal,
        adx: float | None = None,
    ) -> RiskCheckResult:
        """
        Check if market conditions are suitable for grid trading.

        Grid strategies work best in ranging markets. Strong trends
        can cause one-sided fills and growing exposure.

        Args:
            atr: Current ATR value.
            price_move: Absolute price change over ATR period.
            adx: ADX value if available (optional).

        Returns:
            RiskCheckResult with DEACTIVATE if trending too strongly.
        """
        result = RiskCheckResult(action=GridRiskAction.CONTINUE)

        # Check price move vs ATR
        if atr > 0:
            move_ratio = price_move / atr
            if move_ratio >= self._config.trend_atr_multiplier:
                result.action = GridRiskAction.DEACTIVATE
                result.reasons.append(
                    f"Price move {float(move_ratio):.1f}x ATR "
                    f"(threshold: {float(self._config.trend_atr_multiplier):.1f}x)"
                )

        # Check ADX if available
        if adx is not None and adx >= self._config.trend_adx_threshold:
            if result.action != GridRiskAction.DEACTIVATE:
                result.action = GridRiskAction.DEACTIVATE
            result.reasons.append(
                f"ADX {adx:.1f} exceeds threshold {self._config.trend_adx_threshold:.1f}"
            )

        # Warnings for mild trend
        if result.action == GridRiskAction.CONTINUE:
            if atr > 0:
                move_ratio = price_move / atr
                if move_ratio >= self._config.trend_atr_multiplier * Decimal("0.7"):
                    result.warnings.append("Price approaching trend threshold")
            if adx is not None and adx >= self._config.trend_adx_threshold * 0.7:
                result.warnings.append("ADX approaching trend threshold")

        return result

    def classify_trend(
        self,
        atr: Decimal,
        price_move: Decimal,
        adx: float | None = None,
    ) -> TrendState:
        """
        Classify current market trend state.

        Args:
            atr: Current ATR value.
            price_move: Absolute price change.
            adx: ADX value if available.

        Returns:
            TrendState classification.
        """
        if atr <= 0:
            return TrendState.RANGING

        move_ratio = price_move / atr

        if move_ratio >= self._config.trend_atr_multiplier:
            return TrendState.STRONG_TREND
        if adx is not None and adx >= self._config.trend_adx_threshold:
            return TrendState.STRONG_TREND

        threshold_70 = self._config.trend_atr_multiplier * Decimal("0.7")
        if move_ratio >= threshold_70:
            return TrendState.MILD_TREND
        if adx is not None and adx >= self._config.trend_adx_threshold * 0.7:
            return TrendState.MILD_TREND

        return TrendState.RANGING

    # =================================================================
    # Balance Protection
    # =================================================================

    def check_balance(
        self,
        available_balance: Decimal,
        total_balance: Decimal,
    ) -> RiskCheckResult:
        """
        Check if enough balance is kept free.

        Args:
            available_balance: Currently available (free) balance.
            total_balance: Total account balance.

        Returns:
            RiskCheckResult.
        """
        result = RiskCheckResult(action=GridRiskAction.CONTINUE)

        if total_balance <= 0:
            result.action = GridRiskAction.PAUSE
            result.reasons.append("Total balance is zero or negative")
            return result

        free_pct = available_balance / total_balance
        if free_pct < self._config.min_balance_pct:
            result.action = GridRiskAction.PAUSE
            result.reasons.append(
                f"Free balance {float(free_pct):.1%} below minimum "
                f"{float(self._config.min_balance_pct):.1%}"
            )

        return result

    # =================================================================
    # Comprehensive Risk Evaluation
    # =================================================================

    def evaluate_risk(
        self,
        current_price: Decimal,
        current_equity: Decimal,
        current_exposure: Decimal,
        open_orders: int,
        unrealized_pnl: Decimal = Decimal("0"),
        atr: Decimal = Decimal("0"),
        price_move: Decimal = Decimal("0"),
        adx: float | None = None,
        available_balance: Decimal = Decimal("0"),
        total_balance: Decimal = Decimal("0"),
    ) -> RiskCheckResult:
        """
        Run all risk checks and return the most severe result.

        Priority: STOP_LOSS > DEACTIVATE > REDUCE > PAUSE > CONTINUE

        Returns:
            RiskCheckResult with the highest-priority action.
        """
        checks = [
            self.check_grid_stop_loss(current_price, unrealized_pnl=unrealized_pnl),
            self.check_drawdown(current_equity),
            self.check_consecutive_losses(),
        ]

        if atr > 0:
            checks.append(self.check_trend_suitability(atr, price_move, adx))

        if total_balance > 0:
            checks.append(self.check_balance(available_balance, total_balance))

        # Merge all results — pick most severe action
        priority = {
            GridRiskAction.CONTINUE: 0,
            GridRiskAction.PAUSE: 1,
            GridRiskAction.REDUCE: 2,
            GridRiskAction.DEACTIVATE: 3,
            GridRiskAction.STOP_LOSS: 4,
        }

        merged = RiskCheckResult(action=GridRiskAction.CONTINUE)
        for check in checks:
            if priority[check.action] > priority[merged.action]:
                merged.action = check.action
            merged.reasons.extend(check.reasons)
            merged.warnings.extend(check.warnings)

        if merged.reasons:
            logger.warning(
                "Risk check triggered",
                action=merged.action.value,
                reasons=merged.reasons,
            )

        return merged

    # =================================================================
    # State Management
    # =================================================================

    def set_grid_entry_price(self, price: Decimal) -> None:
        """Set the entry price when grid is activated."""
        self._grid_entry_price = price
        self._peak_equity = Decimal("0")
        self._consecutive_losses = 0

    def reset(self) -> None:
        """Reset all risk tracking state."""
        self._peak_equity = Decimal("0")
        self._consecutive_losses = 0
        self._grid_entry_price = Decimal("0")
        self._total_realized_pnl = Decimal("0")

    def get_statistics(self) -> dict[str, Any]:
        """Get risk manager statistics."""
        return {
            "peak_equity": str(self._peak_equity),
            "consecutive_losses": self._consecutive_losses,
            "grid_entry_price": str(self._grid_entry_price),
            "total_realized_pnl": str(self._total_realized_pnl),
            "config": {
                "max_position_size": str(self._config.max_position_size),
                "max_total_exposure": str(self._config.max_total_exposure),
                "max_open_orders": self._config.max_open_orders,
                "grid_stop_loss_pct": str(self._config.grid_stop_loss_pct),
                "max_drawdown_pct": str(self._config.max_drawdown_pct),
            },
        }
