"""
GridBacktestSimulator — Core grid backtest simulation engine.

Composes existing components:
- GridCalculator: level calculation, ATR, bounds
- GridOrderManager: order state, counter-orders, cycle tracking
- MarketSimulator: order execution, fees, balances
- GridRiskManager: stop-loss, drawdown

Simulation loop processes OHLCV candles with intra-candle price sweep:
  open → low → high → close  (or open → high → low → close)
to properly trigger limit orders on both sides.
"""

import asyncio
import math
import time
from decimal import Decimal
from typing import Any

import pandas as pd

from bot.backtesting.grid.models import (
    EquityPoint,
    GridBacktestConfig,
    GridBacktestResult,
    GridDirection,
    GridTradeRecord,
)
from bot.strategies.grid.grid_calculator import (
    GridCalculator,
    GridConfig,
    GridSpacing,
)
from bot.strategies.grid.grid_order_manager import GridOrderManager, OrderStatus
from bot.strategies.grid.grid_risk_manager import (
    GridRiskAction,
    GridRiskConfig,
    GridRiskManager,
)
from bot.tests.backtesting.market_simulator import MarketSimulator


class GridBacktestSimulator:
    """
    Runs a grid backtest on OHLCV candle data.

    Usage:
        config = GridBacktestConfig(symbol="BTCUSDT", num_levels=15)
        simulator = GridBacktestSimulator(config)
        result = simulator.run(candles_df)
    """

    def __init__(self, config: GridBacktestConfig) -> None:
        self.config = config
        self._result: GridBacktestResult | None = None

    def run(self, candles: pd.DataFrame) -> GridBacktestResult:
        """
        Run backtest synchronously (wraps async internally).

        Args:
            candles: DataFrame with columns [timestamp, open, high, low, close, volume].
                     Prices can be float or Decimal.

        Returns:
            GridBacktestResult with all metrics.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context — can't use asyncio.run()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.run_async(candles))
                return future.result()
        else:
            return asyncio.run(self.run_async(candles))

    async def run_async(self, candles: pd.DataFrame) -> GridBacktestResult:
        """
        Run backtest asynchronously.

        Args:
            candles: DataFrame with columns [timestamp, open, high, low, close, volume].

        Returns:
            GridBacktestResult with all metrics.
        """
        start_time = time.perf_counter()

        # Validate input
        required_cols = {"open", "high", "low", "close"}
        missing = required_cols - set(candles.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if len(candles) < 2:
            raise ValueError("Need at least 2 candles")

        # Initialize components
        market = MarketSimulator(
            symbol=self.config.symbol,
            initial_balance_quote=self.config.initial_balance,
            maker_fee=self.config.maker_fee,
            taker_fee=self.config.taker_fee,
        )

        order_mgr = GridOrderManager(symbol=self.config.symbol)

        risk_config = GridRiskConfig(
            grid_stop_loss_pct=self.config.stop_loss_pct,
            max_drawdown_pct=self.config.max_drawdown_pct,
        )
        risk_mgr = GridRiskManager(config=risk_config)

        # Calculate grid bounds
        upper, lower = self._calculate_bounds(candles)

        grid_config = GridConfig(
            upper_price=upper,
            lower_price=lower,
            num_levels=self.config.num_levels,
            spacing=self.config.spacing,
            amount_per_grid=self.config.amount_per_grid,
            profit_per_grid=self.config.profit_per_grid,
        )

        # Get first price for order generation
        first_price = Decimal(str(candles.iloc[0]["close"]))

        # Calculate and place initial orders
        initial_orders = order_mgr.calculate_initial_orders(grid_config, first_price)
        for order_state in initial_orders:
            gl = order_state.grid_level
            try:
                result = await market.create_order(
                    symbol=self.config.symbol,
                    order_type="limit",
                    side=gl.side,
                    amount=gl.amount,
                    price=gl.price,
                )
                order_mgr.register_exchange_order(order_state.id, result["id"])
            except Exception:
                order_mgr.mark_order_failed(order_state.id, "placement_failed")

        # Track state
        risk_mgr.set_grid_entry_price(first_price)
        equity_curve: list[EquityPoint] = []
        trade_history: list[GridTradeRecord] = []
        peak_equity = float(self.config.initial_balance)
        max_drawdown = 0.0
        price_left_grid = 0
        max_buy_exposure = 0.0
        total_fees = 0.0
        filled_levels: set[int] = set()
        stopped = False
        stop_reason = ""
        returns: list[float] = []
        prev_equity = float(self.config.initial_balance)

        # Track initial trades (from orders that filled immediately)
        initial_trade_count = len(market.trade_history)
        for t in market.trade_history[:initial_trade_count]:
            trade_history.append(GridTradeRecord(
                timestamp=t["timestamp"],
                side=t["side"],
                price=t["price"],
                amount=t["amount"],
                fee=t["fee"],
                order_id=t["order_id"],
            ))
            total_fees += t["fee"]

        # Simulation loop
        actual_candles = 0
        for idx in range(len(candles)):
            row = candles.iloc[idx]
            actual_candles += 1
            ts = str(row.get("timestamp", f"candle_{idx}"))
            o = Decimal(str(row["open"]))
            h = Decimal(str(row["high"]))
            l = Decimal(str(row["low"]))  # noqa: E741
            c = Decimal(str(row["close"]))

            # Intra-candle price sweep: open → low → high → close
            # This ensures buy orders trigger on lows and sell orders on highs
            prices = [o, l, h, c]

            trade_count_before = len(market.trade_history)

            for price in prices:
                await market.set_price(price)

            # Check for new fills
            trade_count_after = len(market.trade_history)
            new_trades = market.trade_history[trade_count_before:trade_count_after]

            for t in new_trades:
                trade_history.append(GridTradeRecord(
                    timestamp=ts,
                    side=t["side"],
                    price=t["price"],
                    amount=t["amount"],
                    fee=t["fee"],
                    order_id=t["order_id"],
                ))
                total_fees += t["fee"]

                # Notify order manager and place counter-orders
                exchange_id = t["order_id"]
                counter = order_mgr.on_order_filled(
                    exchange_order_id=exchange_id,
                    filled_price=Decimal(str(t["price"])),
                    filled_amount=Decimal(str(t["amount"])),
                )

                if counter:
                    # Track filled level
                    filled_levels.add(counter.grid_level.index)

                    # Place counter-order
                    try:
                        result = await market.create_order(
                            symbol=self.config.symbol,
                            order_type="limit",
                            side=counter.grid_level.side,
                            amount=counter.grid_level.amount,
                            price=counter.grid_level.price,
                        )
                        order_mgr.register_exchange_order(counter.id, result["id"])
                    except Exception:
                        order_mgr.mark_order_failed(counter.id, "counter_placement_failed")

            # Track exposure
            buy_exposure = sum(
                float(o_state.grid_level.price * o_state.grid_level.amount)
                for o_state in order_mgr.active_orders
                if o_state.grid_level.side == "buy"
            )
            max_buy_exposure = max(max_buy_exposure, buy_exposure)

            # Track price leaving grid
            if float(c) > float(upper) or float(c) < float(lower):
                price_left_grid += 1

            # Calculate equity
            equity = float(market.get_portfolio_value())

            # Track returns for Sharpe
            if prev_equity > 0:
                ret = (equity - prev_equity) / prev_equity
                returns.append(ret)
            prev_equity = equity

            # Track drawdown
            if equity > peak_equity:
                peak_equity = equity
            if peak_equity > 0:
                dd = (peak_equity - equity) / peak_equity
                max_drawdown = max(max_drawdown, dd)

            # Record equity point
            equity_curve.append(EquityPoint(
                timestamp=ts,
                equity=equity,
                price=float(c),
                unrealized_pnl=equity - float(self.config.initial_balance),
            ))

            # Risk check
            risk_result = risk_mgr.evaluate_risk(
                current_price=c,
                current_equity=Decimal(str(equity)),
                current_exposure=Decimal(str(buy_exposure)),
                open_orders=len(order_mgr.active_orders),
            )
            if risk_result.action in (GridRiskAction.STOP_LOSS, GridRiskAction.DEACTIVATE):
                stopped = True
                stop_reason = "; ".join(risk_result.reasons) if risk_result.reasons else risk_result.action.value
                break

        # Calculate final metrics
        final_equity = float(market.get_portfolio_value())
        initial_bal = float(self.config.initial_balance)
        total_pnl = final_equity - initial_bal
        total_return_pct = (total_pnl / initial_bal) * 100 if initial_bal > 0 else 0.0

        completed = order_mgr.completed_cycles
        num_cycles = len(completed)

        # Win rate from completed cycles
        if num_cycles > 0:
            wins = sum(1 for c in completed if c.profit > 0)
            win_rate = wins / num_cycles
            avg_profit = float(sum(c.profit for c in completed)) / num_cycles
        else:
            win_rate = 0.0
            avg_profit = 0.0

        # Grid fill rate
        total_possible_levels = self.config.num_levels
        fill_rate = len(filled_levels) / total_possible_levels if total_possible_levels > 0 else 0.0

        # Profit factor
        gross_profit = sum(float(c.profit) for c in completed if c.profit > 0)
        gross_loss = abs(sum(float(c.profit) for c in completed if c.profit < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

        # Sharpe ratio (annualized, assuming hourly candles by default)
        sharpe = self._calculate_sharpe(returns)
        sortino = self._calculate_sortino(returns)
        calmar = abs(total_return_pct / 100 / max_drawdown) if max_drawdown > 0 else 0.0

        elapsed = time.perf_counter() - start_time

        self._result = GridBacktestResult(
            config=self.config,
            total_return_pct=total_return_pct,
            total_pnl=total_pnl,
            final_equity=final_equity,
            max_drawdown_pct=max_drawdown,
            total_trades=len(trade_history),
            win_rate=win_rate,
            completed_cycles=num_cycles,
            grid_fill_rate=fill_rate,
            avg_profit_per_cycle=avg_profit,
            price_left_grid_count=price_left_grid,
            max_one_sided_exposure=max_buy_exposure,
            total_fees_paid=total_fees,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            profit_factor=profit_factor,
            equity_curve=equity_curve,
            trade_history=trade_history,
            candles_processed=actual_candles,
            stopped_by_risk=stopped,
            stop_reason=stop_reason,
            duration_seconds=elapsed,
        )
        return self._result

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _calculate_bounds(self, candles: pd.DataFrame) -> tuple[Decimal, Decimal]:
        """Calculate grid bounds from config or ATR."""
        if not self.config.auto_bounds:
            upper = self.config.upper_price
            lower = self.config.lower_price
        else:
            # Use first N candles for ATR
            n = min(self.config.atr_period + 1, len(candles))
            subset = candles.iloc[:n]
            highs = [Decimal(str(x)) for x in subset["high"]]
            lows = [Decimal(str(x)) for x in subset["low"]]
            closes = [Decimal(str(x)) for x in subset["close"]]

            atr = GridCalculator.calculate_atr(highs, lows, closes, self.config.atr_period)
            current_price = closes[-1]
            upper, lower = GridCalculator.adjust_bounds_by_atr(
                current_price, atr, self.config.atr_multiplier,
            )

        # Apply direction shift
        if self.config.direction == GridDirection.LONG:
            # Shift bounds down — more buy levels
            spread = upper - lower
            shift = spread * Decimal("0.2")
            upper -= shift
            lower -= shift
        elif self.config.direction == GridDirection.SHORT:
            # Shift bounds up — more sell levels
            spread = upper - lower
            shift = spread * Decimal("0.2")
            upper += shift
            lower += shift

        # Safety: ensure lower > 0
        if lower <= 0:
            lower = Decimal("0.01")

        return upper, lower

    @staticmethod
    def _calculate_sharpe(returns: list[float], periods_per_year: int = 8760) -> float:
        """Calculate annualized Sharpe ratio (assuming hourly candles)."""
        if len(returns) < 2:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_ret = math.sqrt(variance) if variance > 0 else 0.0
        if std_ret == 0:
            return 0.0
        return (mean_ret / std_ret) * math.sqrt(periods_per_year)

    @staticmethod
    def _calculate_sortino(returns: list[float], periods_per_year: int = 8760) -> float:
        """Calculate annualized Sortino ratio."""
        if len(returns) < 2:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        downside = [r for r in returns if r < 0]
        if not downside:
            return float("inf") if mean_ret > 0 else 0.0
        downside_var = sum(r ** 2 for r in downside) / len(downside)
        downside_std = math.sqrt(downside_var) if downside_var > 0 else 0.0
        if downside_std == 0:
            return 0.0
        return (mean_ret / downside_std) * math.sqrt(periods_per_year)
