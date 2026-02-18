"""
GridChartGenerator — Plotly charts for grid backtest results (Issue #8).

Generates:
- Equity curve with price overlay
- Drawdown area chart
- Grid level heatmap (fill frequency)
- Full HTML report combining all charts
"""

from typing import Any

from grid_backtester.engine.models import GridBacktestResult
from grid_backtester.logging import get_logger

logger = get_logger(__name__)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class GridChartGenerator:
    """Generates interactive plotly charts from backtest results."""

    def __init__(self) -> None:
        if not PLOTLY_AVAILABLE:
            logger.warning("plotly not installed — charts will be unavailable")

    def equity_curve_chart(self, result: GridBacktestResult) -> str:
        """Generate equity curve with price overlay as HTML."""
        if not PLOTLY_AVAILABLE:
            return "<p>Chart unavailable: plotly is not installed.</p>"
        if not result.equity_curve:
            return "<p>No equity curve data to display.</p>"

        timestamps = [ep.timestamp for ep in result.equity_curve]
        equities = [ep.equity for ep in result.equity_curve]
        prices = [ep.price for ep in result.equity_curve]

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Scatter(
                x=timestamps, y=equities,
                name="Equity",
                line=dict(color="blue", width=2),
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=timestamps, y=prices,
                name="Price",
                line=dict(color="orange", width=1, dash="dot"),
                opacity=0.7,
            ),
            secondary_y=True,
        )

        fig.update_layout(
            title=f"Equity Curve — {result.config.symbol}",
            xaxis_title="Time",
            height=500,
            template="plotly_white",
        )
        fig.update_yaxes(title_text="Equity ($)", secondary_y=False)
        fig.update_yaxes(title_text="Price", secondary_y=True)

        return fig.to_html(full_html=False, include_plotlyjs="cdn")

    def drawdown_chart(self, result: GridBacktestResult) -> str:
        """Generate drawdown area chart as HTML."""
        if not PLOTLY_AVAILABLE:
            return "<p>Chart unavailable: plotly is not installed.</p>"
        if not result.equity_curve:
            return "<p>No equity curve data to display.</p>"

        timestamps = [ep.timestamp for ep in result.equity_curve]
        equities = [ep.equity for ep in result.equity_curve]

        # Calculate drawdown series
        peak = equities[0]
        drawdowns = []
        for eq in equities:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0.0
            drawdowns.append(-dd)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=timestamps, y=drawdowns,
            fill="tozeroy",
            name="Drawdown",
            line=dict(color="red", width=1),
            fillcolor="rgba(255, 0, 0, 0.2)",
        ))

        fig.update_layout(
            title=f"Drawdown — {result.config.symbol}",
            xaxis_title="Time",
            yaxis_title="Drawdown (%)",
            height=300,
            template="plotly_white",
        )

        return fig.to_html(full_html=False, include_plotlyjs="cdn")

    def grid_heatmap(self, result: GridBacktestResult) -> str:
        """Generate grid level fill frequency heatmap as HTML."""
        if not PLOTLY_AVAILABLE:
            return "<p>Chart unavailable: plotly is not installed.</p>"
        if not result.trade_history:
            return "<p>No trade data to display.</p>"

        # Aggregate trade prices into bins
        buy_prices = [t.price for t in result.trade_history if t.side == "buy"]
        sell_prices = [t.price for t in result.trade_history if t.side == "sell"]

        fig = go.Figure()

        if buy_prices:
            fig.add_trace(go.Histogram(
                x=buy_prices,
                name="Buy Fills",
                marker_color="green",
                opacity=0.7,
                nbinsx=result.config.num_levels,
            ))

        if sell_prices:
            fig.add_trace(go.Histogram(
                x=sell_prices,
                name="Sell Fills",
                marker_color="red",
                opacity=0.7,
                nbinsx=result.config.num_levels,
            ))

        fig.update_layout(
            title=f"Grid Level Fill Frequency — {result.config.symbol}",
            xaxis_title="Price",
            yaxis_title="Fill Count",
            barmode="overlay",
            height=400,
            template="plotly_white",
        )

        return fig.to_html(full_html=False, include_plotlyjs="cdn")

    def full_report_html(self, result: GridBacktestResult) -> str:
        """Generate full HTML report with all charts."""
        metrics = result.to_dict()

        # Build metrics table
        metrics_html = "<table style='border-collapse:collapse;width:100%;max-width:800px;margin:20px auto;'>"
        metrics_html += "<tr><th colspan='2' style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>Backtest Metrics</th></tr>"
        for key, value in metrics.items():
            if key in ("symbol", "timeframe", "stop_reason") and not value:
                continue
            metrics_html += f"<tr><td style='padding:4px 8px;border-bottom:1px solid #eee;'>{key}</td>"
            metrics_html += f"<td style='padding:4px 8px;border-bottom:1px solid #eee;text-align:right;'>{value}</td></tr>"
        metrics_html += "</table>"

        equity_html = self.equity_curve_chart(result)
        drawdown_html = self.drawdown_chart(result)
        heatmap_html = self.grid_heatmap(result)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Grid Backtest Report — {result.config.symbol}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #fafafa; }}
        h1 {{ color: #333; }}
        .chart {{ margin: 20px 0; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <h1>Grid Backtest Report: {result.config.symbol}</h1>
    {metrics_html}
    <div class="chart">{equity_html}</div>
    <div class="chart">{drawdown_html}</div>
    <div class="chart">{heatmap_html}</div>
</body>
</html>"""
