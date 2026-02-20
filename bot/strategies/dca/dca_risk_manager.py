"""
DCA Risk Manager — v2.0.

Controls risk for DCA operations:
- Maximum drawdown limits (per-deal and portfolio)
- Capital allocation and balance protection
- Emergency stop-loss enforcement
- Maximum concurrent positions
- Daily loss limits
- Pump & dump protection (extreme price change detection)
- Consecutive loss tracking

Usage:
    config = DCARiskConfig(max_concurrent_deals=3, ...)
    risk_mgr = DCARiskManager(config)
    result = risk_mgr.evaluate_risk(state)
    if not result.is_safe:
        # Handle risk action
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


# =============================================================================
# Enums
# =============================================================================


class DCARiskAction(str, Enum):
    """Risk action to take."""

    CONTINUE = "continue"  # All clear
    PAUSE = "pause"  # Temporarily stop opening new deals
    CLOSE_DEAL = "close_deal"  # Close specific deal
    CLOSE_ALL = "close_all"  # Emergency: close all deals
    REDUCE = "reduce"  # Reduce position / skip next SO


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class RiskCheckResult:
    """Result of a risk check."""

    action: DCARiskAction = DCARiskAction.CONTINUE
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return self.action == DCARiskAction.CONTINUE

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "is_safe": self.is_safe,
            "reasons": self.reasons,
            "warnings": self.warnings,
        }


@dataclass
class DealRiskState:
    """Risk-relevant state of a single deal."""

    deal_id: str
    symbol: str
    entry_price: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    total_cost: Decimal
    total_volume: Decimal
    safety_orders_filled: int
    max_safety_orders: int
    unrealized_pnl: Decimal = Decimal("0")
    unrealized_pnl_pct: Decimal = Decimal("0")


@dataclass
class PortfolioRiskState:
    """Risk-relevant state of the entire DCA portfolio."""

    active_deals: list[DealRiskState] = field(default_factory=list)
    total_equity: Decimal = Decimal("0")
    available_balance: Decimal = Decimal("0")
    total_balance: Decimal = Decimal("0")
    daily_realized_pnl: Decimal = Decimal("0")
    consecutive_losses: int = 0


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DCARiskConfig:
    """Risk management configuration for DCA strategy."""

    # Position limits
    max_concurrent_deals: int = 3
    max_position_cost: Decimal = Decimal("5000")  # Per deal
    max_total_exposure: Decimal = Decimal("15000")  # All deals combined

    # Stop loss
    deal_stop_loss_pct: Decimal = Decimal("10.0")  # Per-deal SL from base price
    deal_stop_loss_from_average: bool = False  # Measure from avg entry instead

    # Drawdown
    max_deal_drawdown_pct: Decimal = Decimal("15.0")  # Max unrealized loss per deal
    max_portfolio_drawdown_pct: Decimal = Decimal("10.0")  # Max drawdown from peak

    # Daily limits
    max_daily_loss: Decimal = Decimal("500")
    max_consecutive_losses: int = 5

    # Balance protection
    min_balance_pct: Decimal = Decimal("0.20")  # Keep at least 20% free

    # Pump & dump protection
    max_price_change_pct: Decimal = Decimal("10.0")  # Max % change to trigger alert
    pause_on_extreme_volatility: bool = True

    def validate(self) -> None:
        """Validate configuration."""
        if self.max_concurrent_deals < 1:
            raise ValueError("max_concurrent_deals must be >= 1")
        if self.max_position_cost <= 0:
            raise ValueError("max_position_cost must be positive")
        if self.max_total_exposure <= 0:
            raise ValueError("max_total_exposure must be positive")
        if self.deal_stop_loss_pct <= 0:
            raise ValueError("deal_stop_loss_pct must be positive")
        if self.max_deal_drawdown_pct <= 0 or self.max_deal_drawdown_pct > 100:
            raise ValueError("max_deal_drawdown_pct must be between 0 and 100")
        if self.max_portfolio_drawdown_pct <= 0 or self.max_portfolio_drawdown_pct > 100:
            raise ValueError("max_portfolio_drawdown_pct must be between 0 and 100")
        if self.max_daily_loss < 0:
            raise ValueError("max_daily_loss must be >= 0")
        if self.max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be >= 1")
        if self.min_balance_pct < 0 or self.min_balance_pct > 1:
            raise ValueError("min_balance_pct must be between 0 and 1")
        if self.max_price_change_pct <= 0:
            raise ValueError("max_price_change_pct must be positive")


# =============================================================================
# DCA Risk Manager
# =============================================================================


class DCARiskManager:
    """
    Manages risk for DCA strategy.

    Checks:
    1. Concurrent deal limits
    2. Per-deal stop-loss
    3. Per-deal drawdown
    4. Portfolio drawdown
    5. Daily loss limits
    6. Consecutive loss streaks
    7. Balance protection
    8. Extreme price movement (pump & dump)
    """

    def __init__(self, config: DCARiskConfig | None = None):
        self._config = config or DCARiskConfig()
        self._config.validate()
        self._peak_equity = Decimal("0")
        self._consecutive_losses = 0
        self._total_realized_pnl = Decimal("0")
        self._daily_realized_pnl = Decimal("0")

    @property
    def config(self) -> DCARiskConfig:
        return self._config

    # -----------------------------------------------------------------
    # Full Risk Evaluation
    # -----------------------------------------------------------------

    def evaluate_risk(self, state: PortfolioRiskState) -> RiskCheckResult:
        """
        Run all risk checks and return the highest-priority action.

        Priority: CLOSE_ALL > CLOSE_DEAL > REDUCE > PAUSE > CONTINUE.
        """
        all_reasons: list[str] = []
        all_warnings: list[str] = []
        highest_action = DCARiskAction.CONTINUE

        # 1. Per-deal checks
        for deal_state in state.active_deals:
            deal_result = self.check_deal_risk(deal_state)
            if not deal_result.is_safe:
                all_reasons.extend(deal_result.reasons)
                if self._action_priority(deal_result.action) > self._action_priority(
                    highest_action
                ):
                    highest_action = deal_result.action
            all_warnings.extend(deal_result.warnings)

        # 2. Portfolio-level checks
        checks = [
            self.check_concurrent_deals(len(state.active_deals)),
            self.check_portfolio_drawdown(state.total_equity),
            self.check_daily_loss(state.daily_realized_pnl),
            self.check_consecutive_losses(),
            self.check_balance(state.available_balance, state.total_balance),
            self.check_total_exposure(state.active_deals),
        ]

        for check in checks:
            all_warnings.extend(check.warnings)
            if not check.is_safe:
                all_reasons.extend(check.reasons)
                if self._action_priority(check.action) > self._action_priority(highest_action):
                    highest_action = check.action

        return RiskCheckResult(
            action=highest_action,
            reasons=all_reasons,
            warnings=all_warnings,
        )

    # -----------------------------------------------------------------
    # Individual Checks
    # -----------------------------------------------------------------

    def check_deal_risk(self, deal: DealRiskState) -> RiskCheckResult:
        """Check risk for a single deal."""
        reasons: list[str] = []
        warnings: list[str] = []
        action = DCARiskAction.CONTINUE

        # Stop loss
        sl_result = self.check_deal_stop_loss(deal)
        if not sl_result.is_safe:
            reasons.extend(sl_result.reasons)
            action = sl_result.action
        warnings.extend(sl_result.warnings)

        # Drawdown
        dd_result = self.check_deal_drawdown(deal)
        if not dd_result.is_safe:
            reasons.extend(dd_result.reasons)
            if self._action_priority(dd_result.action) > self._action_priority(action):
                action = dd_result.action
        warnings.extend(dd_result.warnings)

        return RiskCheckResult(action=action, reasons=reasons, warnings=warnings)

    def check_deal_stop_loss(self, deal: DealRiskState) -> RiskCheckResult:
        """Check if a deal has hit its stop-loss."""
        cfg = self._config

        if cfg.deal_stop_loss_from_average:
            ref_price = deal.average_entry_price
        else:
            ref_price = deal.entry_price

        if ref_price <= 0:
            return RiskCheckResult()

        loss_pct = ((ref_price - deal.current_price) / ref_price) * 100

        if loss_pct >= cfg.deal_stop_loss_pct:
            return RiskCheckResult(
                action=DCARiskAction.CLOSE_DEAL,
                reasons=[
                    f"Deal {deal.deal_id}: Stop-loss triggered "
                    f"({loss_pct:.1f}% >= {cfg.deal_stop_loss_pct}%)"
                ],
            )

        # Warning at 70%
        warning_threshold = cfg.deal_stop_loss_pct * Decimal("0.7")
        if loss_pct >= warning_threshold:
            return RiskCheckResult(
                warnings=[
                    f"Deal {deal.deal_id}: Approaching stop-loss "
                    f"({loss_pct:.1f}% / {cfg.deal_stop_loss_pct}%)"
                ],
            )

        return RiskCheckResult()

    def check_deal_drawdown(self, deal: DealRiskState) -> RiskCheckResult:
        """Check per-deal unrealized drawdown."""
        cfg = self._config

        if deal.total_cost <= 0:
            return RiskCheckResult()

        dd_pct = abs(deal.unrealized_pnl_pct) if deal.unrealized_pnl < 0 else Decimal("0")

        if dd_pct >= cfg.max_deal_drawdown_pct:
            return RiskCheckResult(
                action=DCARiskAction.CLOSE_DEAL,
                reasons=[
                    f"Deal {deal.deal_id}: Drawdown exceeded "
                    f"({dd_pct:.1f}% >= {cfg.max_deal_drawdown_pct}%)"
                ],
            )

        warning_threshold = cfg.max_deal_drawdown_pct * Decimal("0.7")
        if dd_pct >= warning_threshold:
            return RiskCheckResult(
                warnings=[
                    f"Deal {deal.deal_id}: Drawdown warning "
                    f"({dd_pct:.1f}% / {cfg.max_deal_drawdown_pct}%)"
                ],
            )

        return RiskCheckResult()

    def check_concurrent_deals(self, active_count: int) -> RiskCheckResult:
        """Check if too many deals are open."""
        cfg = self._config

        if active_count >= cfg.max_concurrent_deals:
            return RiskCheckResult(
                action=DCARiskAction.PAUSE,
                reasons=[
                    f"Max concurrent deals reached ({active_count}/{cfg.max_concurrent_deals})"
                ],
            )

        warning_at = max(1, cfg.max_concurrent_deals - 1)
        if active_count >= warning_at:
            return RiskCheckResult(
                warnings=[f"Approaching max deals ({active_count}/{cfg.max_concurrent_deals})"],
            )

        return RiskCheckResult()

    def check_portfolio_drawdown(self, current_equity: Decimal) -> RiskCheckResult:
        """Track peak equity and check portfolio drawdown."""
        cfg = self._config

        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        if self._peak_equity <= 0:
            return RiskCheckResult()

        dd_pct = ((self._peak_equity - current_equity) / self._peak_equity) * 100

        if dd_pct >= cfg.max_portfolio_drawdown_pct:
            return RiskCheckResult(
                action=DCARiskAction.CLOSE_ALL,
                reasons=[
                    f"Portfolio drawdown exceeded ({dd_pct:.1f}% >= {cfg.max_portfolio_drawdown_pct}%)"
                ],
            )

        warning_threshold = cfg.max_portfolio_drawdown_pct * Decimal("0.7")
        if dd_pct >= warning_threshold:
            return RiskCheckResult(
                warnings=[
                    f"Portfolio drawdown warning ({dd_pct:.1f}% / {cfg.max_portfolio_drawdown_pct}%)"
                ],
            )

        return RiskCheckResult()

    def check_daily_loss(self, daily_pnl: Decimal | None = None) -> RiskCheckResult:
        """Check daily realized PnL limit."""
        cfg = self._config
        pnl = daily_pnl if daily_pnl is not None else self._daily_realized_pnl

        if cfg.max_daily_loss > 0 and pnl < -cfg.max_daily_loss:
            return RiskCheckResult(
                action=DCARiskAction.PAUSE,
                reasons=[f"Daily loss exceeded ({pnl} < -{cfg.max_daily_loss})"],
            )

        warning_threshold = -cfg.max_daily_loss * Decimal("0.7")
        if cfg.max_daily_loss > 0 and pnl < warning_threshold:
            return RiskCheckResult(
                warnings=[f"Approaching daily loss limit ({pnl} / -{cfg.max_daily_loss})"],
            )

        return RiskCheckResult()

    def check_consecutive_losses(self) -> RiskCheckResult:
        """Check consecutive loss streak."""
        cfg = self._config

        if self._consecutive_losses >= cfg.max_consecutive_losses:
            return RiskCheckResult(
                action=DCARiskAction.PAUSE,
                reasons=[
                    f"Consecutive losses reached ({self._consecutive_losses} >= {cfg.max_consecutive_losses})"
                ],
            )

        return RiskCheckResult()

    def check_balance(self, available_balance: Decimal, total_balance: Decimal) -> RiskCheckResult:
        """Check minimum free balance threshold."""
        cfg = self._config

        if total_balance <= 0:
            return RiskCheckResult(
                action=DCARiskAction.PAUSE,
                reasons=["Zero total balance"],
            )

        free_ratio = available_balance / total_balance
        if free_ratio < cfg.min_balance_pct:
            return RiskCheckResult(
                action=DCARiskAction.PAUSE,
                reasons=[f"Free balance too low ({free_ratio:.1%} < {cfg.min_balance_pct:.0%})"],
            )

        return RiskCheckResult()

    def check_total_exposure(self, deals: list[DealRiskState]) -> RiskCheckResult:
        """Check total exposure across all deals."""
        cfg = self._config
        total_cost = sum(d.total_cost for d in deals)

        if total_cost > cfg.max_total_exposure:
            return RiskCheckResult(
                action=DCARiskAction.PAUSE,
                reasons=[f"Total exposure exceeded ({total_cost} > {cfg.max_total_exposure})"],
            )

        warning_threshold = cfg.max_total_exposure * Decimal("0.85")
        if total_cost > warning_threshold:
            return RiskCheckResult(
                warnings=[f"Approaching exposure limit ({total_cost} / {cfg.max_total_exposure})"],
            )

        return RiskCheckResult()

    def check_price_change(
        self, previous_price: Decimal, current_price: Decimal
    ) -> RiskCheckResult:
        """
        Check for extreme price movement (pump & dump protection).

        Compares price change against max_price_change_pct threshold.
        """
        cfg = self._config

        if previous_price <= 0:
            return RiskCheckResult()

        change_pct = abs((current_price - previous_price) / previous_price) * 100

        if change_pct >= cfg.max_price_change_pct:
            action = (
                DCARiskAction.PAUSE if cfg.pause_on_extreme_volatility else DCARiskAction.CONTINUE
            )
            return RiskCheckResult(
                action=action,
                reasons=[f"Extreme price change ({change_pct:.1f}% >= {cfg.max_price_change_pct}%)"]
                if action != DCARiskAction.CONTINUE
                else [],
                warnings=[f"Extreme price change detected ({change_pct:.1f}%)"]
                if action == DCARiskAction.CONTINUE
                else [],
            )

        return RiskCheckResult()

    # -----------------------------------------------------------------
    # State Tracking
    # -----------------------------------------------------------------

    def record_trade_result(self, pnl: Decimal) -> None:
        """Record a completed trade result."""
        self._total_realized_pnl += pnl
        self._daily_realized_pnl += pnl
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def reset_daily_pnl(self) -> None:
        """Reset daily PnL counter (call at start of new trading day)."""
        self._daily_realized_pnl = Decimal("0")

    def reset(self) -> None:
        """Reset all internal state."""
        self._peak_equity = Decimal("0")
        self._consecutive_losses = 0
        self._total_realized_pnl = Decimal("0")
        self._daily_realized_pnl = Decimal("0")

    # -----------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------

    def can_open_new_deal(
        self,
        active_deal_count: int,
        deal_cost: Decimal,
        current_exposure: Decimal,
        available_balance: Decimal,
        total_balance: Decimal,
    ) -> RiskCheckResult:
        """
        Quick check whether a new deal can be opened.

        Combines concurrent deal limit, exposure, and balance checks.
        """
        reasons: list[str] = []
        warnings: list[str] = []
        action = DCARiskAction.CONTINUE

        # Concurrent deals
        if active_deal_count >= self._config.max_concurrent_deals:
            action = DCARiskAction.PAUSE
            reasons.append(
                f"Max concurrent deals ({active_deal_count}/{self._config.max_concurrent_deals})"
            )

        # Exposure
        if current_exposure + deal_cost > self._config.max_total_exposure:
            action = DCARiskAction.PAUSE
            reasons.append(
                f"Would exceed exposure limit ({current_exposure + deal_cost} > {self._config.max_total_exposure})"
            )

        # Single deal cost
        if deal_cost > self._config.max_position_cost:
            action = DCARiskAction.PAUSE
            reasons.append(
                f"Deal cost exceeds max ({deal_cost} > {self._config.max_position_cost})"
            )

        # Balance
        if total_balance > 0:
            remaining = available_balance - deal_cost
            remaining_ratio = remaining / total_balance
            if remaining_ratio < self._config.min_balance_pct:
                action = DCARiskAction.PAUSE
                reasons.append(
                    f"Would leave insufficient balance ({remaining_ratio:.1%} < {self._config.min_balance_pct:.0%})"
                )

        # Daily loss
        if (
            self._config.max_daily_loss > 0
            and self._daily_realized_pnl < -self._config.max_daily_loss
        ):
            action = DCARiskAction.PAUSE
            reasons.append("Daily loss limit already exceeded")

        # Consecutive losses
        if self._consecutive_losses >= self._config.max_consecutive_losses:
            action = DCARiskAction.PAUSE
            reasons.append("Consecutive loss limit reached")

        return RiskCheckResult(action=action, reasons=reasons, warnings=warnings)

    def get_statistics(self) -> dict[str, Any]:
        """Return current risk state for monitoring."""
        return {
            "peak_equity": str(self._peak_equity),
            "consecutive_losses": self._consecutive_losses,
            "total_realized_pnl": str(self._total_realized_pnl),
            "daily_realized_pnl": str(self._daily_realized_pnl),
            "config": {
                "max_concurrent_deals": self._config.max_concurrent_deals,
                "max_position_cost": str(self._config.max_position_cost),
                "max_total_exposure": str(self._config.max_total_exposure),
                "deal_stop_loss_pct": str(self._config.deal_stop_loss_pct),
                "max_daily_loss": str(self._config.max_daily_loss),
                "max_consecutive_losses": self._config.max_consecutive_losses,
            },
        }

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    @staticmethod
    def _action_priority(action: DCARiskAction) -> int:
        """Higher number = higher priority."""
        return {
            DCARiskAction.CONTINUE: 0,
            DCARiskAction.PAUSE: 1,
            DCARiskAction.REDUCE: 2,
            DCARiskAction.CLOSE_DEAL: 3,
            DCARiskAction.CLOSE_ALL: 4,
        }.get(action, 0)
