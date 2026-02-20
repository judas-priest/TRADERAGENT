"""
Tests for report generation: HTML reports, SVG charts, strategy-specific metrics.

Issue #175 — Phase 6.4: Report Generation.
"""

import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import pytest

from bot.strategies.base import (
    BaseMarketAnalysis,
    BaseSignal,
    BaseStrategy,
    ExitReason,
    PositionInfo,
    SignalDirection,
    StrategyPerformance,
)
from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.monte_carlo import (
    MonteCarloConfig,
    MonteCarloResult,
    MonteCarloSimulation,
)
from bot.tests.backtesting.multi_tf_data_loader import (
    MultiTimeframeData,
    MultiTimeframeDataLoader,
)
from bot.tests.backtesting.multi_tf_engine import (
    MultiTFBacktestConfig,
    MultiTimeframeBacktestEngine,
)
from bot.tests.backtesting.report_generator import (
    ReportConfig,
    ReportGenerator,
    SVGChartBuilder,
)
from bot.tests.backtesting.strategy_comparison import (
    StrategyComparison,
    StrategyComparisonResult,
)
from bot.tests.backtesting.walk_forward import (
    WalkForwardAnalysis,
    WalkForwardConfig,
    WalkForwardResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SimpleTestStrategy(BaseStrategy):
    """Minimal strategy for report generation tests."""

    def __init__(self, name: str = "test-strategy", buy_every_n: int = 10) -> None:
        self._name = name
        self._buy_every_n = buy_every_n
        self._bar_count = 0
        self._positions: dict[str, dict[str, Any]] = {}

    def get_strategy_name(self) -> str:
        return self._name

    def get_strategy_type(self) -> str:
        return "test"

    def analyze_market(self, *dfs: pd.DataFrame) -> BaseMarketAnalysis:
        return BaseMarketAnalysis(
            trend="sideways",
            trend_strength=0.5,
            volatility=0.01,
            timestamp=datetime.now(timezone.utc),
            strategy_type="test",
        )

    def generate_signal(self, df: pd.DataFrame, current_balance: Decimal) -> Optional[BaseSignal]:
        if df.empty:
            return None
        self._bar_count += 1
        if self._bar_count % self._buy_every_n != 0 or self._positions:
            return None
        if current_balance < Decimal("100"):
            return None
        close = Decimal(str(df["close"].iloc[-1]))
        return BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=close,
            stop_loss=close * Decimal("0.98"),
            take_profit=close * Decimal("1.01"),
            confidence=0.6,
            timestamp=datetime.now(timezone.utc),
            strategy_type="test",
            signal_reason="periodic",
            risk_reward_ratio=0.5,
        )

    def open_position(self, signal: BaseSignal, position_size: Decimal) -> str:
        import uuid

        pos_id = str(uuid.uuid4())[:8]
        self._positions[pos_id] = {
            "direction": signal.direction,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "size": position_size,
            "current_price": signal.entry_price,
        }
        return pos_id

    def update_positions(
        self, current_price: Decimal, df: pd.DataFrame
    ) -> list[tuple[str, ExitReason]]:
        exits = []
        for pos_id, pos in list(self._positions.items()):
            pos["current_price"] = current_price
            if current_price >= pos["take_profit"]:
                exits.append((pos_id, ExitReason.TAKE_PROFIT))
            elif current_price <= pos["stop_loss"]:
                exits.append((pos_id, ExitReason.STOP_LOSS))
        return exits

    def close_position(
        self, position_id: str, exit_reason: ExitReason, exit_price: Decimal
    ) -> None:
        self._positions.pop(position_id, None)

    def get_active_positions(self) -> list[PositionInfo]:
        return []

    def get_performance(self) -> StrategyPerformance:
        return StrategyPerformance()

    def reset(self) -> None:
        self._bar_count = 0
        self._positions.clear()


def _make_backtest_result(
    name: str = "test-strategy",
    trades: list[tuple[float, float]] | None = None,
    initial_balance: float = 10000.0,
) -> BacktestResult:
    """Build a BacktestResult with trade history."""
    if trades is None:
        trades = [
            (45000, 45500),
            (45200, 45600),
            (45100, 44900),
            (44800, 45200),
            (45300, 45100),
            (45000, 45800),
        ]

    history = []
    winning = 0
    losing = 0
    total_pnl = 0.0
    for buy_p, sell_p in trades:
        amount = 0.01
        history.append(
            {"side": "buy", "price": buy_p, "amount": amount, "timestamp": "2024-01-01T00:00:00"}
        )
        history.append(
            {"side": "sell", "price": sell_p, "amount": amount, "timestamp": "2024-01-01T01:00:00"}
        )
        pnl = (sell_p - buy_p) * amount
        total_pnl += pnl
        if pnl > 0:
            winning += 1
        else:
            losing += 1

    total = winning + losing
    now = datetime.now(timezone.utc)

    return BacktestResult(
        strategy_name=name,
        symbol="BTC/USDT",
        start_time=now - timedelta(days=7),
        end_time=now,
        duration=timedelta(days=7),
        initial_balance=Decimal(str(initial_balance)),
        final_balance=Decimal(str(initial_balance + total_pnl)),
        total_return=Decimal(str(total_pnl)),
        total_return_pct=Decimal(str(total_pnl / initial_balance * 100)),
        max_drawdown=Decimal("50"),
        max_drawdown_pct=Decimal("0.5"),
        total_trades=total,
        winning_trades=winning,
        losing_trades=losing,
        win_rate=Decimal(str(winning / total * 100)) if total > 0 else Decimal("0"),
        total_buy_orders=len(trades),
        total_sell_orders=len(trades),
        avg_profit_per_trade=Decimal(str(total_pnl / total)) if total > 0 else Decimal("0"),
        sharpe_ratio=Decimal("1.5"),
        trade_history=history,
        equity_curve=[
            {
                "timestamp": (now - timedelta(hours=i)).isoformat(),
                "price": 45000.0,
                "portfolio_value": initial_balance + i * 10,
            }
            for i in range(50)
        ],
    )


def _load_test_data(days: int = 4) -> MultiTimeframeData:
    loader = MultiTimeframeDataLoader()
    return loader.load(
        symbol="BTC/USDT",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 1) + timedelta(days=days),
        trend="up",
        base_price=Decimal("45000"),
    )


# ===========================================================================
# SVG Chart Builder Tests
# ===========================================================================


class TestSVGChartBuilder:
    def test_line_chart_basic(self):
        chart = SVGChartBuilder(width=400, height=200)
        svg = chart.line_chart([1.0, 2.0, 3.0, 2.5], title="Test")
        assert "<svg" in svg
        assert "Test" in svg
        assert "</svg>" in svg

    def test_line_chart_with_fill(self):
        chart = SVGChartBuilder()
        svg = chart.line_chart([10, 20, 15, 25], title="Filled", fill=True)
        assert 'opacity="0.1"' in svg

    def test_line_chart_empty(self):
        chart = SVGChartBuilder()
        svg = chart.line_chart([], title="Empty")
        assert "No data" in svg

    def test_line_chart_single_value(self):
        chart = SVGChartBuilder()
        svg = chart.line_chart([42.0], title="Single")
        assert "No data" in svg

    def test_multi_line_chart(self):
        chart = SVGChartBuilder()
        svg = chart.multi_line_chart(
            {"A": [1, 2, 3], "B": [3, 2, 1]},
            title="Multi",
        )
        assert "<svg" in svg
        assert "Multi" in svg
        assert "A" in svg
        assert "B" in svg

    def test_multi_line_chart_empty(self):
        chart = SVGChartBuilder()
        svg = chart.multi_line_chart({}, title="Empty")
        assert "No data" in svg

    def test_bar_chart_basic(self):
        chart = SVGChartBuilder()
        svg = chart.bar_chart(["Jan", "Feb", "Mar"], [10, -5, 15], title="Bars")
        assert "<svg" in svg
        assert "Bars" in svg
        assert "#16a34a" in svg  # green for positive
        assert "#dc2626" in svg  # red for negative

    def test_bar_chart_empty(self):
        chart = SVGChartBuilder()
        svg = chart.bar_chart([], [], title="Empty")
        assert "No data" in svg


# ===========================================================================
# Report Config Tests
# ===========================================================================


class TestReportConfig:
    def test_defaults(self):
        cfg = ReportConfig()
        assert cfg.title == "Backtest Report"
        assert cfg.chart_width == 800
        assert cfg.include_equity_chart is True

    def test_custom(self):
        cfg = ReportConfig(title="Custom", chart_width=600, include_trade_history=False)
        assert cfg.title == "Custom"
        assert cfg.chart_width == 600
        assert cfg.include_trade_history is False


# ===========================================================================
# Single Backtest Report Tests
# ===========================================================================


class TestReportGeneratorSingle:
    def test_generate_html(self):
        gen = ReportGenerator()
        html = gen.generate(_make_backtest_result())
        assert "<!DOCTYPE html>" in html
        assert "test-strategy" in html

    def test_contains_metrics(self):
        gen = ReportGenerator()
        html = gen.generate(_make_backtest_result())
        assert "Initial Balance" in html
        assert "Final Balance" in html
        assert "Win Rate" in html

    def test_contains_equity_chart(self):
        gen = ReportGenerator()
        html = gen.generate(_make_backtest_result())
        assert "Equity Curve" in html
        assert "<svg" in html

    def test_contains_drawdown_chart(self):
        gen = ReportGenerator()
        html = gen.generate(_make_backtest_result())
        assert "Drawdown" in html

    def test_contains_trade_table(self):
        gen = ReportGenerator()
        html = gen.generate(_make_backtest_result())
        assert "Trade History" in html

    def test_no_trade_table_when_disabled(self):
        gen = ReportGenerator(config=ReportConfig(include_trade_history=False))
        html = gen.generate(_make_backtest_result())
        assert "Trade History" not in html

    def test_no_equity_chart_when_disabled(self):
        gen = ReportGenerator(config=ReportConfig(include_equity_chart=False))
        html = gen.generate(_make_backtest_result())
        assert "Equity Curve" not in html

    def test_footer_present(self):
        gen = ReportGenerator()
        html = gen.generate(_make_backtest_result())
        assert "TRADERAGENT Backtest Report Generator" in html

    def test_save_to_file(self):
        gen = ReportGenerator()
        html = gen.generate(_make_backtest_result())
        with tempfile.TemporaryDirectory() as tmp:
            path = gen.save(html, f"{tmp}/report.html")
            assert path.exists()
            content = path.read_text()
            assert "<!DOCTYPE html>" in content

    def test_save_creates_subdirs(self):
        gen = ReportGenerator()
        html = gen.generate(_make_backtest_result())
        with tempfile.TemporaryDirectory() as tmp:
            path = gen.save(html, f"{tmp}/sub/dir/report.html")
            assert path.exists()

    def test_sharpe_ratio_shown(self):
        gen = ReportGenerator()
        result = _make_backtest_result()
        html = gen.generate(result)
        assert "Sharpe" in html
        assert "1.5" in html

    def test_no_sharpe_when_none(self):
        result = _make_backtest_result()
        result.sharpe_ratio = None
        gen = ReportGenerator()
        html = gen.generate(result)
        # Should still render without error
        assert "<!DOCTYPE html>" in html


# ===========================================================================
# Comparison Report Tests
# ===========================================================================


class TestReportGeneratorComparison:
    def test_comparison_report(self):
        result_a = _make_backtest_result("StrategyA")
        result_b = _make_backtest_result("StrategyB")
        comparison = StrategyComparisonResult(
            results={"StrategyA": result_a, "StrategyB": result_b},
            rankings={
                "total_return_pct": ["StrategyA", "StrategyB"],
                "win_rate": ["StrategyB", "StrategyA"],
            },
            summary={
                "StrategyA": {
                    "total_return_pct": 2.0,
                    "total_trades": 6,
                    "win_rate": 66.7,
                    "max_drawdown_pct": 0.5,
                    "sharpe_ratio": 1.5,
                },
                "StrategyB": {
                    "total_return_pct": 1.5,
                    "total_trades": 6,
                    "win_rate": 70.0,
                    "max_drawdown_pct": 0.3,
                    "sharpe_ratio": 1.2,
                },
            },
        )
        gen = ReportGenerator()
        html = gen.generate_comparison(comparison)
        assert "Strategy Comparison" in html
        assert "StrategyA" in html
        assert "StrategyB" in html

    def test_comparison_has_equity_overlay(self):
        result_a = _make_backtest_result("A")
        result_b = _make_backtest_result("B")
        comparison = StrategyComparisonResult(
            results={"A": result_a, "B": result_b},
            rankings={},
            summary={
                "A": {
                    "total_return_pct": 1.0,
                    "total_trades": 6,
                    "win_rate": 50.0,
                    "max_drawdown_pct": 0.5,
                    "sharpe_ratio": 1.0,
                },
                "B": {
                    "total_return_pct": 2.0,
                    "total_trades": 6,
                    "win_rate": 60.0,
                    "max_drawdown_pct": 0.3,
                    "sharpe_ratio": 1.5,
                },
            },
        )
        gen = ReportGenerator()
        html = gen.generate_comparison(comparison)
        assert "Equity Curves Comparison" in html

    def test_comparison_rankings_table(self):
        comparison = StrategyComparisonResult(
            results={},
            rankings={"total_return_pct": ["A", "B"]},
            summary={},
        )
        gen = ReportGenerator()
        html = gen.generate_comparison(comparison)
        assert "Rankings" in html


# ===========================================================================
# Monte Carlo Report Tests
# ===========================================================================


class TestReportGeneratorMonteCarlo:
    def test_monte_carlo_report(self):
        bt = _make_backtest_result()
        mc = MonteCarloSimulation(config=MonteCarloConfig(n_simulations=50, seed=42))
        mc_result = mc.run(bt)

        gen = ReportGenerator()
        html = gen.generate_monte_carlo(mc_result)
        assert "Monte Carlo" in html
        assert "Probability of Profit" in html

    def test_monte_carlo_has_var(self):
        bt = _make_backtest_result()
        mc = MonteCarloSimulation(config=MonteCarloConfig(n_simulations=50, seed=42))
        mc_result = mc.run(bt)

        gen = ReportGenerator()
        html = gen.generate_monte_carlo(mc_result)
        assert "VaR" in html
        assert "CVaR" in html

    def test_monte_carlo_has_percentiles(self):
        bt = _make_backtest_result()
        mc = MonteCarloSimulation(config=MonteCarloConfig(n_simulations=50, seed=42))
        mc_result = mc.run(bt)

        gen = ReportGenerator()
        html = gen.generate_monte_carlo(mc_result)
        assert "Return Percentiles" in html
        assert "Max Drawdown Percentiles" in html


# ===========================================================================
# Walk-Forward Report Tests
# ===========================================================================


class TestReportGeneratorWalkForward:
    async def test_walk_forward_report(self):
        data = _load_test_data(days=10)
        wf = WalkForwardAnalysis(
            config=WalkForwardConfig(
                n_splits=2,
                train_pct=0.6,
                backtest_config=MultiTFBacktestConfig(warmup_bars=20),
            )
        )
        strategy = SimpleTestStrategy(buy_every_n=5)
        wf_result = await wf.run(strategy, data)

        gen = ReportGenerator()
        html = gen.generate_walk_forward(wf_result)
        assert "Walk-Forward" in html
        assert "Consistency Ratio" in html

    async def test_walk_forward_has_robustness_badge(self):
        data = _load_test_data(days=10)
        wf = WalkForwardAnalysis(
            config=WalkForwardConfig(
                n_splits=2,
                train_pct=0.6,
                backtest_config=MultiTFBacktestConfig(warmup_bars=20),
            )
        )
        strategy = SimpleTestStrategy(buy_every_n=5)
        wf_result = await wf.run(strategy, data)

        gen = ReportGenerator()
        html = gen.generate_walk_forward(wf_result)
        # Should have either ROBUST or NOT ROBUST badge
        assert "ROBUST" in html or "NOT ROBUST" in html

    async def test_walk_forward_has_window_table(self):
        data = _load_test_data(days=10)
        wf = WalkForwardAnalysis(
            config=WalkForwardConfig(
                n_splits=2,
                train_pct=0.6,
                backtest_config=MultiTFBacktestConfig(warmup_bars=20),
            )
        )
        strategy = SimpleTestStrategy(buy_every_n=5)
        wf_result = await wf.run(strategy, data)

        gen = ReportGenerator()
        html = gen.generate_walk_forward(wf_result)
        assert "Train Return" in html
        assert "Test Return" in html


# ===========================================================================
# Integration: Full pipeline report
# ===========================================================================


class TestReportIntegration:
    async def test_full_pipeline_report(self):
        """Run backtest, generate report, save to file."""
        data = _load_test_data(days=4)
        engine = MultiTimeframeBacktestEngine(
            config=MultiTFBacktestConfig(warmup_bars=20),
        )
        strategy = SimpleTestStrategy(buy_every_n=5)
        result = await engine.run(strategy, data)

        gen = ReportGenerator(config=ReportConfig(title="Pipeline Test"))
        html = gen.generate(result)

        with tempfile.TemporaryDirectory() as tmp:
            path = gen.save(html, f"{tmp}/pipeline_report.html")
            assert path.exists()
            content = path.read_text()
            assert "Pipeline Test" in content
            assert "test-strategy" in content

    async def test_comparison_pipeline(self):
        """Run strategy comparison, generate comparison report."""
        data = _load_test_data(days=4)
        s1 = SimpleTestStrategy(name="fast", buy_every_n=5)
        s2 = SimpleTestStrategy(name="slow", buy_every_n=15)

        comparison = StrategyComparison(
            config=MultiTFBacktestConfig(warmup_bars=20),
        )
        comp_result = await comparison.run([s1, s2], data)

        gen = ReportGenerator()
        html = gen.generate_comparison(comp_result)
        assert "fast" in html
        assert "slow" in html
        assert "Equity Curves Comparison" in html
