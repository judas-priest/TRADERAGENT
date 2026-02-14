"""
Strategy Comparison — Run multiple strategies on same data and compare results.

Produces comparative reports with rankings by various metrics.

Usage:
    comparison = StrategyComparison(config=MultiTFBacktestConfig())
    results = await comparison.run([strategy1, strategy2], data)
    report = comparison.generate_report(results)
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from bot.strategies.base import BaseStrategy
from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.multi_tf_data_loader import (
    MultiTimeframeData,
    MultiTimeframeDataLoader,
)
from bot.tests.backtesting.multi_tf_engine import (
    MultiTFBacktestConfig,
    MultiTimeframeBacktestEngine,
)


@dataclass
class StrategyComparisonResult:
    """Results from comparing multiple strategies."""

    results: dict[str, BacktestResult]
    rankings: dict[str, list[str]]
    summary: dict[str, dict[str, Any]]

    def get_winner(self, metric: str = "total_return_pct") -> str | None:
        """Get the strategy name that ranks first for a given metric."""
        ranking = self.rankings.get(metric, [])
        return ranking[0] if ranking else None


class StrategyComparison:
    """
    Run multiple strategies on the same market data and compare performance.
    """

    def __init__(self, config: MultiTFBacktestConfig | None = None) -> None:
        self.config = config or MultiTFBacktestConfig()

    async def run(
        self,
        strategies: list[BaseStrategy],
        data: MultiTimeframeData,
    ) -> StrategyComparisonResult:
        """
        Run all strategies on the same data and compare results.

        Args:
            strategies: List of BaseStrategy implementations to compare.
            data: Shared MultiTimeframeData for all strategies.

        Returns:
            StrategyComparisonResult with results, rankings, and summary.
        """
        results: dict[str, BacktestResult] = {}

        for strategy in strategies:
            engine = MultiTimeframeBacktestEngine(config=self.config)
            result = await engine.run(strategy, data)
            results[strategy.get_strategy_name()] = result

        rankings = self._compute_rankings(results)
        summary = self._compute_summary(results)

        return StrategyComparisonResult(
            results=results,
            rankings=rankings,
            summary=summary,
        )

    async def run_with_generated_data(
        self,
        strategies: list[BaseStrategy],
        start_date: datetime,
        end_date: datetime,
        trend: str = "up",
        base_price: Decimal = Decimal("45000"),
    ) -> StrategyComparisonResult:
        """Convenience: generate data and run comparison."""
        loader = MultiTimeframeDataLoader()
        data = loader.load(
            symbol=self.config.symbol,
            start_date=start_date,
            end_date=end_date,
            trend=trend,
            base_price=base_price,
        )
        return await self.run(strategies, data)

    def _compute_rankings(
        self, results: dict[str, BacktestResult]
    ) -> dict[str, list[str]]:
        """Compute rankings for each metric (higher is better, except drawdown)."""
        if not results:
            return {}

        metrics = {
            "total_return_pct": True,  # higher is better
            "win_rate": True,
            "total_trades": True,
            "max_drawdown_pct": False,  # lower is better
        }

        rankings: dict[str, list[str]] = {}

        for metric, higher_is_better in metrics.items():
            items = []
            for name, result in results.items():
                value = getattr(result, metric, Decimal("0"))
                items.append((name, float(value)))

            items.sort(key=lambda x: x[1], reverse=higher_is_better)
            rankings[metric] = [name for name, _ in items]

        # Sharpe ratio ranking (higher is better, handle None)
        sharpe_items = []
        for name, result in results.items():
            sr = result.sharpe_ratio
            sharpe_items.append((name, float(sr) if sr is not None else float("-inf")))
        sharpe_items.sort(key=lambda x: x[1], reverse=True)
        rankings["sharpe_ratio"] = [name for name, _ in sharpe_items]

        return rankings

    def _compute_summary(
        self, results: dict[str, BacktestResult]
    ) -> dict[str, dict[str, Any]]:
        """Compute summary statistics for each strategy."""
        summary: dict[str, dict[str, Any]] = {}

        for name, result in results.items():
            summary[name] = {
                "total_return_pct": float(result.total_return_pct),
                "final_balance": float(result.final_balance),
                "total_trades": result.total_trades,
                "win_rate": float(result.win_rate),
                "max_drawdown_pct": float(result.max_drawdown_pct),
                "sharpe_ratio": float(result.sharpe_ratio)
                if result.sharpe_ratio is not None
                else None,
                "avg_profit_per_trade": float(result.avg_profit_per_trade),
                "buy_orders": result.total_buy_orders,
                "sell_orders": result.total_sell_orders,
            }

        return summary

    @staticmethod
    def format_report(comparison: StrategyComparisonResult) -> str:
        """Format comparison result as a human-readable report."""
        lines = []
        lines.append("=" * 70)
        lines.append("STRATEGY COMPARISON REPORT")
        lines.append("=" * 70)

        # Summary table
        lines.append("\nPerformance Summary:")
        lines.append("-" * 70)
        header = f"{'Strategy':<20} {'Return%':>10} {'Trades':>8} {'Win%':>8} {'DD%':>8} {'Sharpe':>8}"
        lines.append(header)
        lines.append("-" * 70)

        for name, stats in comparison.summary.items():
            sharpe_str = f"{stats['sharpe_ratio']:.2f}" if stats["sharpe_ratio"] is not None else "N/A"
            line = (
                f"{name:<20} "
                f"{stats['total_return_pct']:>9.2f}% "
                f"{stats['total_trades']:>8d} "
                f"{stats['win_rate']:>7.1f}% "
                f"{stats['max_drawdown_pct']:>7.2f}% "
                f"{sharpe_str:>8s}"
            )
            lines.append(line)

        # Rankings
        lines.append("\nRankings:")
        lines.append("-" * 70)
        for metric, ranking in comparison.rankings.items():
            ranked = ", ".join(f"{i+1}.{n}" for i, n in enumerate(ranking))
            lines.append(f"  {metric}: {ranked}")

        # Winner
        winner = comparison.get_winner("total_return_pct")
        if winner:
            lines.append(f"\nBest overall return: {winner}")

        lines.append("=" * 70)
        return "\n".join(lines)
