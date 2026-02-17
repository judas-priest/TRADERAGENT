"""Tests for GridChartGenerator — Plotly chart generation."""

import pytest

from grid_backtester.engine.models import (
    EquityPoint,
    GridBacktestConfig,
    GridBacktestResult,
    GridTradeRecord,
)
from grid_backtester.visualization.charts import GridChartGenerator, PLOTLY_AVAILABLE


@pytest.fixture
def sample_result() -> GridBacktestResult:
    """Create a sample backtest result with equity curve and trades."""
    config = GridBacktestConfig(symbol="BTCUSDT")
    return GridBacktestResult(
        config=config,
        total_return_pct=5.0,
        total_pnl=500.0,
        final_equity=10500.0,
        max_drawdown_pct=0.02,
        total_trades=20,
        win_rate=0.6,
        completed_cycles=10,
        sharpe_ratio=1.5,
        equity_curve=[
            EquityPoint(timestamp=f"t{i}", equity=10000 + i * 50, price=45000 + i * 10)
            for i in range(20)
        ],
        trade_history=[
            GridTradeRecord(
                timestamp=f"t{i}",
                side="buy" if i % 2 == 0 else "sell",
                price=45000 + i * 10,
                amount=0.01,
                fee=0.01,
                order_id=f"ord_{i}",
                grid_level=i % 10,
            )
            for i in range(20)
        ],
    )


@pytest.fixture
def empty_result() -> GridBacktestResult:
    return GridBacktestResult()


class TestGridChartGenerator:

    def test_equity_curve_chart(self, sample_result):
        gen = GridChartGenerator()
        html = gen.equity_curve_chart(sample_result)
        if PLOTLY_AVAILABLE:
            assert "Equity" in html
            assert "plotly" in html.lower() or "plotlyjs" in html.lower()
        else:
            assert "No equity curve" in html

    def test_equity_curve_empty(self, empty_result):
        gen = GridChartGenerator()
        html = gen.equity_curve_chart(empty_result)
        assert "No equity curve" in html or "plotly" in html.lower()

    def test_drawdown_chart(self, sample_result):
        gen = GridChartGenerator()
        html = gen.drawdown_chart(sample_result)
        if PLOTLY_AVAILABLE:
            assert "Drawdown" in html
        else:
            assert "No equity curve" in html

    def test_drawdown_chart_empty(self, empty_result):
        gen = GridChartGenerator()
        html = gen.drawdown_chart(empty_result)
        assert "No equity curve" in html or "Drawdown" in html

    def test_grid_heatmap(self, sample_result):
        gen = GridChartGenerator()
        html = gen.grid_heatmap(sample_result)
        if PLOTLY_AVAILABLE:
            assert "Fill" in html or "plotly" in html.lower()
        else:
            assert "No trade data" in html

    def test_grid_heatmap_empty(self, empty_result):
        gen = GridChartGenerator()
        html = gen.grid_heatmap(empty_result)
        assert "No trade data" in html or "plotly" in html.lower()

    def test_full_report_html(self, sample_result):
        gen = GridChartGenerator()
        html = gen.full_report_html(sample_result)
        assert "<!DOCTYPE html>" in html
        assert "BTCUSDT" in html
        assert "Backtest Metrics" in html
        assert "Grid Backtest Report" in html

    def test_full_report_contains_all_sections(self, sample_result):
        gen = GridChartGenerator()
        html = gen.full_report_html(sample_result)
        # Should contain metrics table
        assert "total_return_pct" in html
        # Should contain chart divs
        assert 'class="chart"' in html

    def test_full_report_empty_result(self, empty_result):
        gen = GridChartGenerator()
        html = gen.full_report_html(empty_result)
        assert "<!DOCTYPE html>" in html
        assert "UNKNOWN" in html or "Grid Backtest Report" in html
