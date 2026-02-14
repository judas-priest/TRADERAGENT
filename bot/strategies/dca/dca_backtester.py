"""
DCA Backtester — v2.0.

Simulates DCA deal lifecycle on historical price data to compare
exit strategies (Fixed TP vs Trailing Stop).

Usage:
    backtester = DCABacktester(order_config, trailing_config)
    result = backtester.run(prices)
    print(result.summary())
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from bot.strategies.dca.dca_position_manager import DCAOrderConfig, DCAPositionManager
from bot.strategies.dca.dca_trailing_stop import (
    DCATrailingStop,
    TrailingStopConfig,
    TrailingStopSnapshot,
)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class BacktestTrade:
    """Record of a completed backtest trade."""

    entry_price: Decimal
    exit_price: Decimal
    exit_reason: str
    safety_orders_filled: int
    profit: Decimal
    profit_pct: Decimal
    total_cost: Decimal


@dataclass
class BacktestResult:
    """Aggregate results of a backtest run."""

    trades: list[BacktestTrade] = field(default_factory=list)
    label: str = ""

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.trades if t.profit > 0)

    @property
    def losing_trades(self) -> int:
        return sum(1 for t in self.trades if t.profit <= 0)

    @property
    def win_rate(self) -> Decimal:
        if not self.trades:
            return Decimal("0")
        return Decimal(str(self.winning_trades)) / Decimal(str(self.total_trades))

    @property
    def total_profit(self) -> Decimal:
        return sum((t.profit for t in self.trades), Decimal("0"))

    @property
    def avg_profit_pct(self) -> Decimal:
        if not self.trades:
            return Decimal("0")
        return sum((t.profit_pct for t in self.trades), Decimal("0")) / Decimal(
            str(self.total_trades)
        )

    @property
    def max_profit_pct(self) -> Decimal:
        if not self.trades:
            return Decimal("0")
        return max(t.profit_pct for t in self.trades)

    @property
    def max_loss_pct(self) -> Decimal:
        if not self.trades:
            return Decimal("0")
        return min(t.profit_pct for t in self.trades)

    @property
    def profit_factor(self) -> Decimal:
        gross_profit = sum(
            (t.profit for t in self.trades if t.profit > 0), Decimal("0")
        )
        gross_loss = abs(
            sum((t.profit for t in self.trades if t.profit < 0), Decimal("0"))
        )
        if gross_loss == 0:
            return Decimal("999") if gross_profit > 0 else Decimal("0")
        return gross_profit / gross_loss

    def summary(self) -> dict[str, Any]:
        """Return summary statistics."""
        return {
            "label": self.label,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": str(self.win_rate),
            "total_profit": str(self.total_profit),
            "avg_profit_pct": str(self.avg_profit_pct),
            "max_profit_pct": str(self.max_profit_pct),
            "max_loss_pct": str(self.max_loss_pct),
            "profit_factor": str(self.profit_factor),
        }


# =============================================================================
# DCA Backtester
# =============================================================================


class DCABacktester:
    """
    Simulates DCA deals on a price series.

    For each deal:
    1. Opens base order at trigger price
    2. Fills safety orders as price drops
    3. Exits via trailing stop, fixed TP, or stop loss

    The backtester opens a new deal when no deal is active,
    simulating continuous operation.
    """

    def __init__(
        self,
        order_config: DCAOrderConfig | None = None,
        trailing_config: TrailingStopConfig | None = None,
        label: str = "",
    ):
        self._order_config = order_config or DCAOrderConfig()
        self._trailing_config = trailing_config or TrailingStopConfig()
        self._trailing_stop = DCATrailingStop(self._trailing_config)
        self._label = label

    def run(self, prices: list[Decimal]) -> BacktestResult:
        """
        Run backtest on a price series.

        Args:
            prices: List of prices (chronological order).

        Returns:
            BacktestResult with all completed trades.
        """
        result = BacktestResult(label=self._label)
        pos_mgr = DCAPositionManager("BACKTEST", self._order_config)

        deal = None
        snapshot = None
        i = 0

        while i < len(prices):
            price = prices[i]

            if deal is None:
                # Open new deal
                deal = pos_mgr.open_deal(price)
                snapshot = TrailingStopSnapshot(highest_price_since_entry=price)
                i += 1
                continue

            # Update highest price
            pos_mgr.update_highest_price(deal.id, price)
            deal = pos_mgr.get_deal(deal.id)

            # Check safety orders
            so_trigger = pos_mgr.check_safety_order_trigger(deal.id, price)
            if so_trigger is not None:
                pos_mgr.fill_safety_order(deal.id, so_trigger.level, price)
                deal = pos_mgr.get_deal(deal.id)

            # Check exit conditions
            exit_reason = self._check_exit(deal, price, snapshot)

            if exit_reason is not None:
                close_result = pos_mgr.close_deal(deal.id, price, exit_reason)
                result.trades.append(
                    BacktestTrade(
                        entry_price=deal.base_order_price,
                        exit_price=price,
                        exit_reason=exit_reason,
                        safety_orders_filled=deal.safety_orders_filled,
                        profit=close_result.realized_profit,
                        profit_pct=close_result.realized_profit_pct,
                        total_cost=deal.total_cost,
                    )
                )
                deal = None
                snapshot = None

            i += 1

        return result

    def _check_exit(
        self,
        deal: Any,
        current_price: Decimal,
        snapshot: TrailingStopSnapshot | None,
    ) -> str | None:
        """Check all exit conditions. Returns reason or None."""

        # Trailing stop
        if self._trailing_stop.enabled:
            ts_result = self._trailing_stop.evaluate(
                current_price=current_price,
                average_entry=deal.average_entry_price,
                highest_price=deal.highest_price_since_entry,
                snapshot=snapshot,
            )
            if ts_result.should_exit:
                return "trailing_stop"

        # Fixed take profit (when trailing not enabled)
        if not self._trailing_stop.enabled:
            tp_pct = self._order_config.take_profit_pct
            tp_price = deal.average_entry_price * (1 + tp_pct / 100)
            if current_price >= tp_price:
                return "take_profit"

        # Stop loss (always active)
        sl_pct = self._order_config.stop_loss_pct
        sl_price = deal.average_entry_price * (1 - sl_pct / 100)
        if current_price <= sl_price:
            return "stop_loss"

        return None


def compare_strategies(
    prices: list[Decimal],
    order_config: DCAOrderConfig | None = None,
    trailing_config: TrailingStopConfig | None = None,
) -> dict[str, BacktestResult]:
    """
    Compare Fixed TP vs Trailing Stop on the same price data.

    Returns dict with "fixed_tp" and "trailing_stop" results.
    """
    cfg = order_config or DCAOrderConfig()

    # Fixed TP backtester (trailing disabled)
    fixed_bt = DCABacktester(
        order_config=cfg,
        trailing_config=TrailingStopConfig(enabled=False),
        label="Fixed TP",
    )

    # Trailing stop backtester
    ts_config = trailing_config or TrailingStopConfig()
    trailing_bt = DCABacktester(
        order_config=cfg,
        trailing_config=ts_config,
        label="Trailing Stop",
    )

    return {
        "fixed_tp": fixed_bt.run(prices),
        "trailing_stop": trailing_bt.run(prices),
    }
