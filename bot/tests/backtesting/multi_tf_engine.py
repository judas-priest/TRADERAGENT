"""
Multi-timeframe backtest engine that drives BaseStrategy implementations.

Iterates M5 candles as the finest granularity, builds rolling DataFrames
for each timeframe (D1, H4, H1, M15, M5), and executes the full
BaseStrategy lifecycle:
analyze_market → generate_signal → open_position → update_positions → close_position.

Usage:
    engine = MultiTimeframeBacktestEngine()
    result = await engine.run(strategy, data)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from bot.strategies.base import BaseStrategy, ExitReason, SignalDirection
from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.market_simulator import MarketSimulator
from bot.tests.backtesting.multi_tf_data_loader import (
    MultiTimeframeData,
    MultiTimeframeDataLoader,
)

logger = logging.getLogger(__name__)


@dataclass
class MultiTFBacktestConfig:
    """Configuration for multi-timeframe backtest."""

    symbol: str = "BTC/USDT"
    initial_balance: Decimal = Decimal("10000")
    lookback: int = 100
    warmup_bars: int = 50
    analyze_every_n: int = 4
    risk_per_trade: Decimal = Decimal("0.02")
    max_position_pct: Decimal = Decimal("0.5")


class MultiTimeframeBacktestEngine:
    """
    Backtest engine that executes BaseStrategy with multi-timeframe data.

    Execution loop (per M15 candle after warmup):
        1. Build rolling context DataFrames for D1, H4, H1, M15
        2. Set current price on MarketSimulator
        3. Periodically call strategy.analyze_market(df_d1, df_h4, df_h1, df_m15)
        4. Call strategy.generate_signal(df_m15, current_balance)
        5. If signal, open position + place order via simulator
        6. Call strategy.update_positions(current_price, df_m15)
        7. If exits, close positions + execute sell via simulator
        8. Record equity curve point
    """

    def __init__(self, config: MultiTFBacktestConfig | None = None) -> None:
        self.config = config or MultiTFBacktestConfig()
        self.data_loader = MultiTimeframeDataLoader()
        self._position_amounts: dict[str, Decimal] = {}
        self._position_directions: dict[str, SignalDirection] = {}

    async def run(
        self,
        strategy: BaseStrategy,
        data: MultiTimeframeData,
    ) -> BacktestResult:
        """
        Run a full multi-timeframe backtest.

        Args:
            strategy: A BaseStrategy implementation.
            data: Pre-loaded MultiTimeframeData.

        Returns:
            BacktestResult with full metrics.
        """
        # Reset strategy state
        strategy.reset()

        # Create fresh simulator
        simulator = MarketSimulator(
            symbol=self.config.symbol,
            initial_balance_quote=self.config.initial_balance,
        )

        # Run execution loop
        equity_curve, max_drawdown = await self._execute_loop(strategy, data, simulator)

        # Build result — use the finest-resolution TF for time range
        base_df = data.m5
        return self._build_result(
            strategy_name=strategy.get_strategy_name(),
            simulator=simulator,
            equity_curve=equity_curve,
            max_drawdown=max_drawdown,
            start_time=base_df.index[0].to_pydatetime(),
            end_time=base_df.index[-1].to_pydatetime(),
        )

    async def run_with_generated_data(
        self,
        strategy: BaseStrategy,
        start_date: datetime,
        end_date: datetime,
        trend: str = "up",
        base_price: Decimal = Decimal("45000"),
    ) -> BacktestResult:
        """Convenience: generate data and run backtest."""
        data = self.data_loader.load(
            symbol=self.config.symbol,
            start_date=start_date,
            end_date=end_date,
            trend=trend,
            base_price=base_price,
        )
        return await self.run(strategy, data)

    async def _execute_loop(
        self,
        strategy: BaseStrategy,
        data: MultiTimeframeData,
        simulator: MarketSimulator,
    ) -> tuple[list[dict[str, Any]], Decimal]:
        """
        Core execution loop.

        Returns:
            (equity_curve, max_drawdown)
        """
        equity_curve: list[dict[str, Any]] = []
        peak_value = self.config.initial_balance
        max_drawdown = Decimal("0")
        self._position_amounts = {}
        self._position_directions = {}

        # Iterate over the finest-resolution TF (M5)
        base_df = data.m5
        total_bars = len(base_df)

        for i in range(self.config.warmup_bars, total_bars):
            # Get rolling context — 5 DataFrames
            df_d1, df_h4, df_h1, df_m15, df_m5 = self.data_loader.get_context_at(
                data, base_index=i, lookback=self.config.lookback
            )

            # Current price from M5 close
            current_price = Decimal(str(base_df.iloc[i]["close"]))
            await simulator.set_price(current_price)

            # Periodically analyze market — pass all 5 TFs
            if (i - self.config.warmup_bars) % self.config.analyze_every_n == 0:
                try:
                    strategy.analyze_market(df_d1, df_h4, df_h1, df_m15, df_m5)
                except Exception as e:
                    logger.debug("analyze_market error at bar %d: %s", i, e)

            # Generate signal using the finest TF
            try:
                balance = simulator.get_portfolio_value()
                signal = strategy.generate_signal(df_m5, balance)
            except Exception as e:
                logger.debug("generate_signal error at bar %d: %s", i, e)
                signal = None

            # Open position if signal
            if signal is not None:
                await self._handle_signal_execution(strategy, signal, current_price, simulator)

            # Update positions and handle exits
            try:
                exits = strategy.update_positions(current_price, df_m5)
            except Exception as e:
                logger.debug("update_positions error at bar %d: %s", i, e)
                exits = []

            if exits:
                await self._handle_exits(strategy, exits, current_price, simulator)

            # Record equity curve
            portfolio_value = simulator.get_portfolio_value()
            equity_curve.append(
                {
                    "timestamp": base_df.index[i].isoformat(),
                    "price": float(current_price),
                    "portfolio_value": float(portfolio_value),
                }
            )

            # Update drawdown
            if portfolio_value > peak_value:
                peak_value = portfolio_value
            else:
                drawdown = peak_value - portfolio_value
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

            # Yield to event loop
            await asyncio.sleep(0)

        return equity_curve, max_drawdown

    async def _handle_signal_execution(
        self,
        strategy: BaseStrategy,
        signal: Any,
        current_price: Decimal,
        simulator: MarketSimulator,
    ) -> None:
        """Open position in strategy and place market order on simulator."""
        # Calculate position size
        balance = simulator.get_portfolio_value()
        position_size = self._calculate_position_size(signal, balance, current_price)
        if position_size <= 0:
            return

        # Check if we can afford this
        cost = position_size * current_price
        if cost > simulator.balance.quote:
            return

        try:
            # Open position in strategy
            pos_id = strategy.open_position(signal, cost)

            # Place order on simulator based on direction
            if signal.direction == SignalDirection.LONG:
                await simulator.create_order(
                    symbol=self.config.symbol,
                    order_type="market",
                    side="buy",
                    amount=position_size,
                )
            else:
                # SHORT: sell to open
                await simulator.create_order(
                    symbol=self.config.symbol,
                    order_type="market",
                    side="sell",
                    amount=position_size,
                )

            # Track amount and direction for closing later
            self._position_amounts[pos_id] = position_size
            self._position_directions[pos_id] = signal.direction
        except Exception as e:
            logger.debug("Signal execution failed: %s", e)

    async def _handle_exits(
        self,
        strategy: BaseStrategy,
        exits: list[tuple[str, ExitReason]],
        current_price: Decimal,
        simulator: MarketSimulator,
    ) -> None:
        """Close positions in strategy and execute orders on simulator."""
        for pos_id, exit_reason in exits:
            amount = self._position_amounts.pop(pos_id, None)
            direction = self._position_directions.pop(pos_id, SignalDirection.LONG)
            if amount is None:
                continue

            try:
                # Close in strategy
                strategy.close_position(pos_id, exit_reason, current_price)

                if direction == SignalDirection.LONG:
                    # LONG exit: sell base
                    if simulator.balance.base >= amount:
                        await simulator.create_order(
                            symbol=self.config.symbol,
                            order_type="market",
                            side="sell",
                            amount=amount,
                        )
                else:
                    # SHORT exit: buy to close
                    await simulator.create_order(
                        symbol=self.config.symbol,
                        order_type="market",
                        side="buy",
                        amount=amount,
                    )
            except Exception as e:
                logger.debug("Exit execution failed for %s: %s", pos_id, e)

    def _calculate_position_size(
        self,
        signal: Any,
        current_balance: Decimal,
        current_price: Decimal,
    ) -> Decimal:
        """Calculate position size in base currency."""
        risk_amount = current_balance * self.config.risk_per_trade
        stop_distance = abs(signal.entry_price - signal.stop_loss)

        if stop_distance <= 0:
            return Decimal("0")

        # Position value based on risk
        position_value = (risk_amount / stop_distance) * current_price

        # Cap at max percentage of balance
        max_value = current_balance * self.config.max_position_pct
        position_value = min(position_value, max_value)

        # Convert to base currency amount
        if current_price <= 0:
            return Decimal("0")

        return position_value / current_price

    def _build_result(
        self,
        strategy_name: str,
        simulator: MarketSimulator,
        equity_curve: list[dict[str, Any]],
        max_drawdown: Decimal,
        start_time: datetime,
        end_time: datetime,
    ) -> BacktestResult:
        """Build BacktestResult from simulator state."""
        trade_history = simulator.get_trade_history()
        final_balance = simulator.get_portfolio_value()
        initial = self.config.initial_balance
        total_return = final_balance - initial
        total_return_pct = (
            (total_return / initial) * Decimal("100") if initial > 0 else Decimal("0")
        )
        max_drawdown_pct = (
            (max_drawdown / initial) * Decimal("100") if initial > 0 else Decimal("0")
        )

        # Analyze trades
        buy_orders = [t for t in trade_history if t["side"] == "buy"]
        sell_orders = [t for t in trade_history if t["side"] == "sell"]
        winning_trades = 0
        losing_trades = 0
        total_profit = Decimal("0")

        for i in range(min(len(buy_orders), len(sell_orders))):
            buy_price = Decimal(str(buy_orders[i]["price"]))
            sell_price = Decimal(str(sell_orders[i]["price"]))
            amount = Decimal(str(buy_orders[i]["amount"]))
            profit = (sell_price - buy_price) * amount
            total_profit += profit
            if profit > 0:
                winning_trades += 1
            else:
                losing_trades += 1

        total_trades = winning_trades + losing_trades
        win_rate = (
            Decimal(winning_trades) / Decimal(total_trades) * Decimal("100")
            if total_trades > 0
            else Decimal("0")
        )
        avg_profit = total_profit / Decimal(total_trades) if total_trades > 0 else Decimal("0")

        # Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)

        return BacktestResult(
            strategy_name=strategy_name,
            symbol=self.config.symbol,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            initial_balance=initial,
            final_balance=final_balance,
            total_return=total_return,
            total_return_pct=total_return_pct,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_buy_orders=len(buy_orders),
            total_sell_orders=len(sell_orders),
            avg_profit_per_trade=avg_profit,
            sharpe_ratio=sharpe_ratio,
            trade_history=trade_history,
            equity_curve=equity_curve,
        )

    def _calculate_sharpe_ratio(self, equity_curve: list[dict[str, Any]]) -> Decimal | None:
        """Calculate Sharpe ratio from equity curve."""
        if len(equity_curve) < 2:
            return None

        returns = []
        for i in range(1, len(equity_curve)):
            prev = Decimal(str(equity_curve[i - 1]["portfolio_value"]))
            curr = Decimal(str(equity_curve[i]["portfolio_value"]))
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return None

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_return = variance.sqrt() if variance > 0 else Decimal("0")

        if std_return > 0:
            sharpe = mean_return / std_return
            # Annualize (assuming 5-minute returns: 365 * 24 * 12)
            sharpe = sharpe * Decimal(str((365 * 24 * 12) ** 0.5))
            return sharpe

        return None
