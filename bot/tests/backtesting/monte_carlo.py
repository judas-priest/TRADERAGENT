"""
Monte Carlo Simulation — Bootstrap analysis for trading strategy robustness.

Reshuffles trade returns from a backtest to simulate alternative equity paths
and derive confidence intervals for key performance metrics.

Usage:
    mc = MonteCarloSimulation(n_simulations=1000)
    result = mc.run(backtest_result)
"""

import random
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from bot.tests.backtesting.backtesting_engine import BacktestResult


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo simulation."""

    n_simulations: int = 1000
    seed: int | None = None
    confidence_levels: list[float] = field(
        default_factory=lambda: [0.05, 0.25, 0.50, 0.75, 0.95]
    )


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""

    n_simulations: int
    original_return_pct: float
    original_max_drawdown_pct: float

    # Distribution of final returns (percentiles)
    return_percentiles: dict[float, float]
    # Distribution of max drawdown (percentiles)
    drawdown_percentiles: dict[float, float]
    # Distribution of win rate (percentiles)
    win_rate_percentiles: dict[float, float]

    # Probability of profit
    probability_of_profit: float
    # Probability of exceeding original drawdown
    probability_of_worse_drawdown: float

    # Raw simulation paths for external analysis
    simulated_returns: list[float] = field(default_factory=list)
    simulated_drawdowns: list[float] = field(default_factory=list)

    def get_var(self, confidence: float = 0.05) -> float:
        """Value at Risk: worst return at given confidence level."""
        return self.return_percentiles.get(confidence, 0.0)

    def get_cvar(self, confidence: float = 0.05) -> float:
        """Conditional VaR: average return below VaR threshold."""
        var = self.get_var(confidence)
        below = [r for r in self.simulated_returns if r <= var]
        return sum(below) / len(below) if below else var


class MonteCarloSimulation:
    """
    Monte Carlo analysis via bootstrap resampling of trade returns.

    Takes a BacktestResult, extracts per-trade returns, reshuffles them
    to generate alternative equity paths, and computes statistics.
    """

    def __init__(self, config: MonteCarloConfig | None = None) -> None:
        self.config = config or MonteCarloConfig()

    def run(self, backtest_result: BacktestResult) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on backtest results.

        Extracts trade-level returns, then for each simulation:
        - Randomly reshuffle trade order
        - Compute equity curve from reshuffled trades
        - Record final return and max drawdown

        Args:
            backtest_result: A completed BacktestResult.

        Returns:
            MonteCarloResult with distributions and confidence intervals.
        """
        trade_returns = self._extract_trade_returns(backtest_result)

        if not trade_returns:
            return self._empty_result(backtest_result)

        rng = random.Random(self.config.seed)

        simulated_returns: list[float] = []
        simulated_drawdowns: list[float] = []
        simulated_win_rates: list[float] = []

        for _ in range(self.config.n_simulations):
            shuffled = trade_returns.copy()
            rng.shuffle(shuffled)

            final_return, max_dd, win_rate = self._simulate_path(
                shuffled, float(backtest_result.initial_balance)
            )
            simulated_returns.append(final_return)
            simulated_drawdowns.append(max_dd)
            simulated_win_rates.append(win_rate)

        # Compute percentiles
        return_pcts = self._percentiles(simulated_returns)
        dd_pcts = self._percentiles(simulated_drawdowns)
        wr_pcts = self._percentiles(simulated_win_rates)

        # Probability metrics
        prob_profit = sum(1 for r in simulated_returns if r > 0) / len(simulated_returns)
        orig_dd = float(backtest_result.max_drawdown_pct)
        prob_worse_dd = sum(
            1 for d in simulated_drawdowns if d > orig_dd
        ) / len(simulated_drawdowns)

        return MonteCarloResult(
            n_simulations=self.config.n_simulations,
            original_return_pct=float(backtest_result.total_return_pct),
            original_max_drawdown_pct=orig_dd,
            return_percentiles=return_pcts,
            drawdown_percentiles=dd_pcts,
            win_rate_percentiles=wr_pcts,
            probability_of_profit=prob_profit,
            probability_of_worse_drawdown=prob_worse_dd,
            simulated_returns=simulated_returns,
            simulated_drawdowns=simulated_drawdowns,
        )

    def _extract_trade_returns(
        self, result: BacktestResult
    ) -> list[float]:
        """Extract per-trade return percentages from trade history."""
        history = result.trade_history
        if not history:
            return []

        buys = [t for t in history if t["side"] == "buy"]
        sells = [t for t in history if t["side"] == "sell"]

        returns = []
        for i in range(min(len(buys), len(sells))):
            buy_price = float(buys[i]["price"])
            sell_price = float(sells[i]["price"])
            if buy_price > 0:
                ret_pct = ((sell_price - buy_price) / buy_price) * 100
                returns.append(ret_pct)

        return returns

    def _simulate_path(
        self, trade_returns: list[float], initial_balance: float
    ) -> tuple[float, float, float]:
        """
        Simulate an equity path from reshuffled trade returns.

        Returns:
            (final_return_pct, max_drawdown_pct, win_rate)
        """
        balance = initial_balance
        peak = balance
        max_dd = 0.0
        wins = 0

        for ret_pct in trade_returns:
            pnl = balance * (ret_pct / 100.0)
            balance += pnl
            if ret_pct > 0:
                wins += 1

            if balance > peak:
                peak = balance
            elif peak > 0:
                dd_pct = ((peak - balance) / peak) * 100
                max_dd = max(max_dd, dd_pct)

        final_return_pct = ((balance - initial_balance) / initial_balance) * 100
        win_rate = (wins / len(trade_returns) * 100) if trade_returns else 0.0

        return final_return_pct, max_dd, win_rate

    def _percentiles(self, values: list[float]) -> dict[float, float]:
        """Compute percentiles for configured confidence levels."""
        if not values:
            return {level: 0.0 for level in self.config.confidence_levels}

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        result = {}
        for level in self.config.confidence_levels:
            idx = min(int(level * n), n - 1)
            result[level] = sorted_vals[idx]
        return result

    def _empty_result(self, result: BacktestResult) -> MonteCarloResult:
        """Return empty result when no trades available."""
        empty_pcts = {level: 0.0 for level in self.config.confidence_levels}
        return MonteCarloResult(
            n_simulations=0,
            original_return_pct=float(result.total_return_pct),
            original_max_drawdown_pct=float(result.max_drawdown_pct),
            return_percentiles=empty_pcts,
            drawdown_percentiles=empty_pcts,
            win_rate_percentiles=empty_pcts,
            probability_of_profit=0.0,
            probability_of_worse_drawdown=0.0,
        )
