"""
GridBacktestSimulator — Core grid backtest simulation engine.

Composes existing components:
- GridCalculator: level calculation, ATR, bounds
- GridOrderManager: order state, counter-orders, cycle tracking
- MarketSimulator: order execution, fees, balances
- GridRiskManager: stop-loss, drawdown
- TrailingGridManager: dynamic grid shifting (optional)

Features:
- Take-profit exit (Issue #2)
- Capital efficiency tracking (Issue #6)
- Trailing grid support (Issue #4)
- Structured logging (Issue #3)
"""

import asyncio
import math
import time
from decimal import Decimal
from typing import Any

import pandas as pd

from grid_backtester.core.calculator import (
    GridCalculator,
    GridConfig,
    GridSpacing,
)
from grid_backtester.core.order_manager import GridOrderManager, OrderStatus
from grid_backtester.core.risk_manager import (
    GridRiskAction,
    GridRiskConfig,
    GridRiskManager,
)
from grid_backtester.core.market_simulator import MarketSimulator
from grid_backtester.engine.models import (
    EquityPoint,
    GridBacktestConfig,
    GridBacktestResult,
    GridDirection,
    GridTradeRecord,
)
from grid_backtester.trailing.manager import TrailingGridManager
from grid_backtester.caching.indicator_cache import IndicatorCache
from grid_backtester.logging import get_logger

logger = get_logger(__name__)


class GridBacktestSimulator:
    """
    Runs a grid backtest on OHLCV candle data.

    Usage:
        config = GridBacktestConfig(symbol="BTCUSDT", num_levels=15)
        simulator = GridBacktestSimulator(config)
        result = simulator.run(candles_df)
    """

    def __init__(self, config: GridBacktestConfig, indicator_cache: IndicatorCache | None = None) -> None:
        self.config = config
        self.indicator_cache = indicator_cache
        self._result: GridBacktestResult | None = None

    def run(self, candles: pd.DataFrame) -> GridBacktestResult:
        """Run backtest synchronously (wraps async internally)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.run_async(candles))
                return future.result()
        else:
            return asyncio.run(self.run_async(candles))

    async def run_async(self, candles: pd.DataFrame) -> GridBacktestResult:
        """Run backtest asynchronously."""
        start_time = time.perf_counter()

        # Validate input
        required_cols = {"open", "high", "low", "close"}
        missing = required_cols - set(candles.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if len(candles) < 2:
            raise ValueError("Need at least 2 candles")

        logger.info(
            "Starting grid backtest",
            symbol=self.config.symbol,
            candles=len(candles),
            num_levels=self.config.num_levels,
            spacing=self.config.spacing.value,
            take_profit_pct=float(self.config.take_profit_pct),
            trailing_enabled=self.config.trailing_enabled,
        )

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

        logger.debug(
            "Grid bounds calculated",
            upper=float(upper),
            lower=float(lower),
            auto_bounds=self.config.auto_bounds,
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

        logger.info(
            "Initial orders placed",
            total=len(initial_orders),
        )

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

        # Capital efficiency tracking (Issue #6)
        total_deployed_capital_candles = 0.0
        initial_bal = float(self.config.initial_balance)

        # Trailing grid manager (Issue #4)
        trailing_mgr = TrailingGridManager(
            shift_threshold_pct=self.config.trailing_shift_threshold_pct,
            recenter_mode=self.config.trailing_recenter_mode,
            cooldown_candles=self.config.trailing_cooldown_candles,
            atr_period=self.config.atr_period,
            atr_multiplier=self.config.atr_multiplier,
        ) if self.config.trailing_enabled else None

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

            # Intra-candle price sweep: open -> low -> high -> close
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
                    filled_levels.add(counter.grid_level.index)

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

            # Capital efficiency: track deployed capital per candle (Issue #6)
            deployed_capital = buy_exposure + sum(
                float(o_state.grid_level.price * o_state.grid_level.amount)
                for o_state in order_mgr.active_orders
                if o_state.grid_level.side == "sell"
            )
            total_deployed_capital_candles += deployed_capital

            # Track price leaving grid
            if float(c) > float(upper) or float(c) < float(lower):
                price_left_grid += 1

            # Trailing grid logic (Issue #4) — delegated to TrailingGridManager
            if trailing_mgr is not None:
                # Build recent price history for ATR mode
                hist_start = max(0, idx - self.config.atr_period)
                hist_slice = candles.iloc[hist_start:idx + 1]
                recent_highs = [Decimal(str(x)) for x in hist_slice["high"]]
                recent_lows = [Decimal(str(x)) for x in hist_slice["low"]]
                recent_closes = [Decimal(str(x)) for x in hist_slice["close"]]

                new_grid_config = trailing_mgr.check_and_shift(
                    current_price=c,
                    current_upper=upper,
                    current_lower=lower,
                    grid_config=grid_config,
                    highs=recent_highs,
                    lows=recent_lows,
                    closes=recent_closes,
                )

                if new_grid_config is not None:
                    upper = new_grid_config.upper_price
                    lower = new_grid_config.lower_price
                    grid_config = new_grid_config

                    # Cancel old orders and place new ones
                    to_cancel, new_orders = order_mgr.rebalance(new_grid_config, c)
                    for cancel_order in to_cancel:
                        if cancel_order.exchange_order_id:
                            try:
                                await market.cancel_order(cancel_order.exchange_order_id)
                            except Exception as e:
                                logger.debug("Failed to cancel order during trailing shift", error=str(e))

                    for new_order in new_orders:
                        gl = new_order.grid_level
                        try:
                            result = await market.create_order(
                                symbol=self.config.symbol,
                                order_type="limit",
                                side=gl.side,
                                amount=gl.amount,
                                price=gl.price,
                            )
                            order_mgr.register_exchange_order(new_order.id, result["id"])
                        except Exception as e:
                            logger.debug("Failed to place trailing order", error=str(e))
                            order_mgr.mark_order_failed(new_order.id, "trailing_placement_failed")

                trailing_mgr.tick()

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
                unrealized_pnl=equity - initial_bal,
            ))

            # Take-profit check (Issue #2)
            if self.config.take_profit_pct > 0 and initial_bal > 0:
                current_pnl_pct = (equity - initial_bal) / initial_bal
                if current_pnl_pct >= float(self.config.take_profit_pct):
                    stopped = True
                    stop_reason = "take_profit_reached"
                    logger.info(
                        "Take-profit triggered",
                        pnl_pct=round(current_pnl_pct * 100, 2),
                        target_pct=float(self.config.take_profit_pct) * 100,
                        candle=idx,
                    )
                    break

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
                logger.warning(
                    "Risk stop triggered",
                    action=risk_result.action.value,
                    reasons=risk_result.reasons,
                    candle=idx,
                )
                break

        # Calculate final metrics
        final_equity = float(market.get_portfolio_value())
        total_pnl = final_equity - initial_bal
        total_return_pct = (total_pnl / initial_bal) * 100 if initial_bal > 0 else 0.0

        completed = order_mgr.completed_cycles
        num_cycles = len(completed)

        if num_cycles > 0:
            wins = sum(1 for c in completed if c.profit > 0)
            win_rate = wins / num_cycles
            avg_profit = float(sum(c.profit for c in completed)) / num_cycles
        else:
            win_rate = 0.0
            avg_profit = 0.0

        total_possible_levels = self.config.num_levels
        fill_rate = len(filled_levels) / total_possible_levels if total_possible_levels > 0 else 0.0

        gross_profit = sum(float(c.profit) for c in completed if c.profit > 0)
        gross_loss = abs(sum(float(c.profit) for c in completed if c.profit < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

        sharpe = self._calculate_sharpe(returns)
        sortino = self._calculate_sortino(returns)
        calmar = abs(total_return_pct / 100 / max_drawdown) if max_drawdown > 0 else 0.0

        # Capital efficiency (Issue #6)
        capital_efficiency = 0.0
        if actual_candles > 0 and initial_bal > 0:
            capital_efficiency = total_deployed_capital_candles / (initial_bal * actual_candles)

        elapsed = time.perf_counter() - start_time

        logger.info(
            "Backtest completed",
            symbol=self.config.symbol,
            candles=actual_candles,
            return_pct=round(total_return_pct, 2),
            cycles=num_cycles,
            max_drawdown=round(max_drawdown * 100, 2),
            capital_efficiency=round(capital_efficiency, 4),
            duration_s=round(elapsed, 2),
            stopped=stopped,
            stop_reason=stop_reason,
        )

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
            capital_efficiency=capital_efficiency,
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
            n = min(self.config.atr_period + 1, len(candles))
            subset = candles.iloc[:n]
            highs = [Decimal(str(x)) for x in subset["high"]]
            lows = [Decimal(str(x)) for x in subset["low"]]
            closes = [Decimal(str(x)) for x in subset["close"]]

            if self.indicator_cache is not None:
                data_hash = IndicatorCache.hash_data([float(x) for x in closes])
                cache_key = IndicatorCache.make_key("atr", data_hash, period=self.config.atr_period)
                atr = self.indicator_cache.get_or_compute(
                    cache_key,
                    lambda: GridCalculator.calculate_atr(highs, lows, closes, self.config.atr_period),
                )
            else:
                atr = GridCalculator.calculate_atr(highs, lows, closes, self.config.atr_period)

            current_price = closes[-1]

            # Fallback: if ATR rounds to zero, use 1% of current price
            if atr <= 0:
                atr = (current_price * Decimal("0.01")).quantize(Decimal("0.01"))
                if atr <= 0:
                    atr = Decimal("0.01")

            upper, lower = GridCalculator.adjust_bounds_by_atr(
                current_price, atr, self.config.atr_multiplier,
            )

        # Apply direction shift
        if self.config.direction == GridDirection.LONG:
            spread = upper - lower
            shift = spread * Decimal("0.2")
            upper -= shift
            lower -= shift
        elif self.config.direction == GridDirection.SHORT:
            spread = upper - lower
            shift = spread * Decimal("0.2")
            upper += shift
            lower += shift

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
