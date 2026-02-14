"""
Report Generator — HTML reports with charts for backtest results.

Produces self-contained HTML reports with embedded SVG charts for
equity curves, drawdown analysis, trade distributions, and strategy
comparisons. Suitable for GitHub Pages publication.

Usage:
    gen = ReportGenerator()
    html = gen.generate(backtest_result)
    gen.save(html, "report.html")
"""

import html as html_mod
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.monte_carlo import MonteCarloResult
from bot.tests.backtesting.strategy_comparison import StrategyComparisonResult
from bot.tests.backtesting.walk_forward import WalkForwardResult


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    title: str = "Backtest Report"
    chart_width: int = 800
    chart_height: int = 300
    include_trade_history: bool = True
    include_equity_chart: bool = True
    include_drawdown_chart: bool = True
    include_distribution_chart: bool = True
    max_trades_in_table: int = 50


class SVGChartBuilder:
    """Builds simple SVG charts for embedding in HTML reports."""

    def __init__(self, width: int = 800, height: int = 300) -> None:
        self.width = width
        self.height = height
        self.padding = 60

    def line_chart(
        self,
        values: list[float],
        labels: list[str] | None = None,
        title: str = "",
        color: str = "#2563eb",
        y_label: str = "",
        fill: bool = False,
    ) -> str:
        """Generate SVG line chart."""
        if not values or len(values) < 2:
            return self._empty_chart(title)

        w = self.width
        h = self.height
        p = self.padding

        min_v = min(values)
        max_v = max(values)
        v_range = max_v - min_v if max_v != min_v else 1.0

        plot_w = w - 2 * p
        plot_h = h - 2 * p

        points = []
        for i, v in enumerate(values):
            x = p + (i / (len(values) - 1)) * plot_w
            y = h - p - ((v - min_v) / v_range) * plot_h
            points.append((x, y))

        path_d = " ".join(
            f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
            for i, (x, y) in enumerate(points)
        )

        fill_path = ""
        if fill:
            fill_d = path_d + f" L{points[-1][0]:.1f},{h - p:.1f} L{points[0][0]:.1f},{h - p:.1f} Z"
            fill_path = f'<path d="{fill_d}" fill="{color}" opacity="0.1"/>'

        # Y-axis labels
        y_labels_svg = ""
        for i in range(5):
            y_val = min_v + (v_range * i / 4)
            y_pos = h - p - (i / 4) * plot_h
            y_labels_svg += (
                f'<text x="{p - 5}" y="{y_pos:.1f}" '
                f'text-anchor="end" font-size="11" fill="#666">'
                f'{y_val:,.1f}</text>'
            )

        return f"""<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h}" fill="#fafafa" rx="8"/>
  <text x="{w // 2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#333">{html_mod.escape(title)}</text>
  {y_labels_svg}
  <text x="15" y="{h // 2}" text-anchor="middle" font-size="11" fill="#666" transform="rotate(-90 15 {h // 2})">{html_mod.escape(y_label)}</text>
  <line x1="{p}" y1="{p}" x2="{p}" y2="{h - p}" stroke="#ddd" stroke-width="1"/>
  <line x1="{p}" y1="{h - p}" x2="{w - p}" y2="{h - p}" stroke="#ddd" stroke-width="1"/>
  {fill_path}
  <path d="{path_d}" fill="none" stroke="{color}" stroke-width="2"/>
</svg>"""

    def multi_line_chart(
        self,
        series: dict[str, list[float]],
        title: str = "",
        y_label: str = "",
    ) -> str:
        """Generate SVG with multiple overlaid line series."""
        colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c"]

        if not series:
            return self._empty_chart(title)

        all_vals = [v for vals in series.values() for v in vals]
        if not all_vals:
            return self._empty_chart(title)

        w = self.width
        h = self.height
        p = self.padding

        min_v = min(all_vals)
        max_v = max(all_vals)
        v_range = max_v - min_v if max_v != min_v else 1.0

        plot_w = w - 2 * p
        plot_h = h - 2 * p

        paths = []
        legend_items = []
        for idx, (name, values) in enumerate(series.items()):
            if len(values) < 2:
                continue
            color = colors[idx % len(colors)]
            points = []
            for i, v in enumerate(values):
                x = p + (i / (len(values) - 1)) * plot_w
                y = h - p - ((v - min_v) / v_range) * plot_h
                points.append(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}")
            paths.append(
                f'<path d="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>'
            )
            lx = p + idx * 150
            legend_items.append(
                f'<rect x="{lx}" y="{h - 15}" width="12" height="12" fill="{color}"/>'
                f'<text x="{lx + 16}" y="{h - 5}" font-size="11" fill="#333">{html_mod.escape(name)}</text>'
            )

        # Y-axis labels
        y_labels_svg = ""
        for i in range(5):
            y_val = min_v + (v_range * i / 4)
            y_pos = h - p - (i / 4) * plot_h
            y_labels_svg += (
                f'<text x="{p - 5}" y="{y_pos:.1f}" '
                f'text-anchor="end" font-size="11" fill="#666">'
                f'{y_val:,.1f}</text>'
            )

        return f"""<svg width="{w}" height="{h + 25}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h + 25}" fill="#fafafa" rx="8"/>
  <text x="{w // 2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#333">{html_mod.escape(title)}</text>
  {y_labels_svg}
  <line x1="{p}" y1="{p}" x2="{p}" y2="{h - p}" stroke="#ddd" stroke-width="1"/>
  <line x1="{p}" y1="{h - p}" x2="{w - p}" y2="{h - p}" stroke="#ddd" stroke-width="1"/>
  {"".join(paths)}
  {"".join(legend_items)}
</svg>"""

    def bar_chart(
        self,
        labels: list[str],
        values: list[float],
        title: str = "",
        color: str = "#2563eb",
        y_label: str = "",
    ) -> str:
        """Generate SVG bar chart."""
        if not values:
            return self._empty_chart(title)

        w = self.width
        h = self.height
        p = self.padding

        min_v = min(0, min(values))
        max_v = max(0, max(values))
        v_range = max_v - min_v if max_v != min_v else 1.0

        plot_w = w - 2 * p
        plot_h = h - 2 * p
        bar_w = plot_w / len(values) * 0.7
        gap = plot_w / len(values) * 0.3

        bars = []
        zero_y = h - p - ((0 - min_v) / v_range) * plot_h

        for i, v in enumerate(values):
            x = p + i * (bar_w + gap) + gap / 2
            y = h - p - ((v - min_v) / v_range) * plot_h
            bar_h = abs(y - zero_y)
            bar_y = min(y, zero_y)
            bar_color = "#16a34a" if v >= 0 else "#dc2626"
            bars.append(
                f'<rect x="{x:.1f}" y="{bar_y:.1f}" width="{bar_w:.1f}" '
                f'height="{bar_h:.1f}" fill="{bar_color}" rx="2"/>'
            )
            # Label
            label = labels[i] if i < len(labels) else ""
            bars.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{h - p + 15}" '
                f'text-anchor="middle" font-size="10" fill="#666">{html_mod.escape(label[:10])}</text>'
            )

        return f"""<svg width="{w}" height="{h + 20}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h + 20}" fill="#fafafa" rx="8"/>
  <text x="{w // 2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#333">{html_mod.escape(title)}</text>
  <line x1="{p}" y1="{zero_y:.1f}" x2="{w - p}" y2="{zero_y:.1f}" stroke="#999" stroke-width="1" stroke-dasharray="4"/>
  {"".join(bars)}
</svg>"""

    def _empty_chart(self, title: str) -> str:
        return (
            f'<svg width="{self.width}" height="{self.height}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{self.width}" height="{self.height}" fill="#fafafa" rx="8"/>'
            f'<text x="{self.width // 2}" y="{self.height // 2}" text-anchor="middle" '
            f'font-size="14" fill="#999">{html_mod.escape(title)} — No data</text></svg>'
        )


class ReportGenerator:
    """
    Generates self-contained HTML reports for backtest results.

    Reports include embedded SVG charts and styled tables.
    """

    def __init__(self, config: ReportConfig | None = None) -> None:
        self.config = config or ReportConfig()
        self.chart = SVGChartBuilder(
            width=self.config.chart_width,
            height=self.config.chart_height,
        )

    def generate(self, result: BacktestResult) -> str:
        """Generate a complete HTML report for a single backtest."""
        sections = [
            self._summary_section(result),
            self._metrics_table(result),
        ]

        if self.config.include_equity_chart and result.equity_curve:
            sections.append(self._equity_chart(result))

        if self.config.include_drawdown_chart and result.equity_curve:
            sections.append(self._drawdown_chart(result))

        if self.config.include_trade_history and result.trade_history:
            sections.append(self._trade_table(result))

        return self._wrap_html(
            title=f"{self.config.title} — {result.strategy_name}",
            body="\n".join(sections),
        )

    def generate_comparison(
        self, comparison: StrategyComparisonResult
    ) -> str:
        """Generate HTML report comparing multiple strategies."""
        sections = [self._comparison_summary(comparison)]

        # Overlay equity curves
        series = {}
        for name, result in comparison.results.items():
            if result.equity_curve:
                series[name] = [
                    e["portfolio_value"] for e in result.equity_curve
                ]
        if series:
            sections.append(
                '<div class="chart">'
                + self.chart.multi_line_chart(
                    series, title="Equity Curves Comparison", y_label="Portfolio Value ($)"
                )
                + "</div>"
            )

        # Rankings table
        sections.append(self._rankings_table(comparison))

        # Per-strategy details
        for name, result in comparison.results.items():
            sections.append(f'<h2>Strategy: {html_mod.escape(name)}</h2>')
            sections.append(self._metrics_table(result))

        return self._wrap_html(
            title=f"{self.config.title} — Strategy Comparison",
            body="\n".join(sections),
        )

    def generate_monte_carlo(self, mc_result: MonteCarloResult) -> str:
        """Generate HTML report for Monte Carlo simulation."""
        sections = [
            '<h2>Monte Carlo Simulation</h2>',
            f'<p>Simulations: <strong>{mc_result.n_simulations}</strong> | '
            f'Original Return: <strong>{mc_result.original_return_pct:.2f}%</strong> | '
            f'Probability of Profit: <strong>{mc_result.probability_of_profit:.1%}</strong></p>',
        ]

        # Return distribution histogram (approximation via bar chart)
        if mc_result.simulated_returns:
            sections.append(self._distribution_chart(
                mc_result.simulated_returns,
                title="Return Distribution (%)",
            ))

        # Percentile tables
        sections.append(self._percentile_table(
            "Return Percentiles (%)", mc_result.return_percentiles
        ))
        sections.append(self._percentile_table(
            "Max Drawdown Percentiles (%)", mc_result.drawdown_percentiles
        ))

        # VaR / CVaR
        var_5 = mc_result.get_var(0.05)
        cvar_5 = mc_result.get_cvar(0.05)
        sections.append(
            f'<div class="metrics"><p>VaR (5%): <strong>{var_5:.2f}%</strong> | '
            f'CVaR (5%): <strong>{cvar_5:.2f}%</strong></p></div>'
        )

        return self._wrap_html(
            title=f"{self.config.title} — Monte Carlo",
            body="\n".join(sections),
        )

    def generate_walk_forward(self, wf_result: WalkForwardResult) -> str:
        """Generate HTML report for walk-forward analysis."""
        sections = [
            '<h2>Walk-Forward Analysis</h2>',
            f'<p>Windows: <strong>{len(wf_result.windows)}</strong> | '
            f'Consistency Ratio: <strong>{wf_result.consistency_ratio:.1%}</strong> | '
            f'Aggregate Test Return: <strong>{float(wf_result.aggregate_test_return_pct):.2f}%</strong></p>',
        ]

        # Per-window results table
        rows = []
        for w in wf_result.windows:
            rows.append(
                f"<tr><td>{w.window_index}</td>"
                f"<td>{float(w.train_result.total_return_pct):.2f}%</td>"
                f"<td>{float(w.test_result.total_return_pct):.2f}%</td>"
                f"<td>{float(w.test_result.win_rate):.1f}%</td>"
                f"<td>{float(w.test_result.max_drawdown_pct):.2f}%</td></tr>"
            )

        sections.append(
            '<table><thead><tr>'
            '<th>Window</th><th>Train Return</th><th>Test Return</th>'
            '<th>Test Win Rate</th><th>Test Max DD</th>'
            '</tr></thead><tbody>'
            + "\n".join(rows)
            + '</tbody></table>'
        )

        # Chart: test returns per window
        if wf_result.windows:
            test_returns = [
                float(w.test_result.total_return_pct) for w in wf_result.windows
            ]
            labels = [f"W{w.window_index}" for w in wf_result.windows]
            sections.append(
                '<div class="chart">'
                + self.chart.bar_chart(
                    labels, test_returns,
                    title="Out-of-Sample Returns by Window",
                    y_label="Return (%)",
                )
                + "</div>"
            )

        robust = wf_result.is_robust()
        badge_class = "badge-green" if robust else "badge-red"
        badge_text = "ROBUST" if robust else "NOT ROBUST"
        sections.append(
            f'<p>Robustness: <span class="{badge_class}">{badge_text}</span></p>'
        )

        return self._wrap_html(
            title=f"{self.config.title} — Walk-Forward",
            body="\n".join(sections),
        )

    def save(self, html_content: str, filepath: str | Path) -> Path:
        """Save HTML report to file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html_content, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Internal section builders
    # ------------------------------------------------------------------

    def _summary_section(self, result: BacktestResult) -> str:
        ret_class = "positive" if result.total_return_pct >= 0 else "negative"
        return (
            f'<div class="summary">'
            f'<h1>{html_mod.escape(result.strategy_name)}</h1>'
            f'<p>{html_mod.escape(result.symbol)} | '
            f'{result.start_time.strftime("%Y-%m-%d")} to {result.end_time.strftime("%Y-%m-%d")} | '
            f'{result.duration.days}d</p>'
            f'<div class="stat-cards">'
            f'<div class="card"><span class="label">Return</span>'
            f'<span class="value {ret_class}">{float(result.total_return_pct):.2f}%</span></div>'
            f'<div class="card"><span class="label">Final Balance</span>'
            f'<span class="value">${float(result.final_balance):,.2f}</span></div>'
            f'<div class="card"><span class="label">Trades</span>'
            f'<span class="value">{result.total_trades}</span></div>'
            f'<div class="card"><span class="label">Win Rate</span>'
            f'<span class="value">{float(result.win_rate):.1f}%</span></div>'
            f'<div class="card"><span class="label">Max DD</span>'
            f'<span class="value negative">{float(result.max_drawdown_pct):.2f}%</span></div>'
            f'<div class="card"><span class="label">Sharpe</span>'
            f'<span class="value">{float(result.sharpe_ratio):.4f}</span></div>'
            f'</div></div>'
        ) if result.sharpe_ratio else (
            f'<div class="summary">'
            f'<h1>{html_mod.escape(result.strategy_name)}</h1>'
            f'<p>{html_mod.escape(result.symbol)} | '
            f'{result.start_time.strftime("%Y-%m-%d")} to {result.end_time.strftime("%Y-%m-%d")} | '
            f'{result.duration.days}d</p>'
            f'<div class="stat-cards">'
            f'<div class="card"><span class="label">Return</span>'
            f'<span class="value {ret_class}">{float(result.total_return_pct):.2f}%</span></div>'
            f'<div class="card"><span class="label">Final Balance</span>'
            f'<span class="value">${float(result.final_balance):,.2f}</span></div>'
            f'<div class="card"><span class="label">Trades</span>'
            f'<span class="value">{result.total_trades}</span></div>'
            f'<div class="card"><span class="label">Win Rate</span>'
            f'<span class="value">{float(result.win_rate):.1f}%</span></div>'
            f'<div class="card"><span class="label">Max DD</span>'
            f'<span class="value negative">{float(result.max_drawdown_pct):.2f}%</span></div>'
            f'</div></div>'
        )

    def _metrics_table(self, result: BacktestResult) -> str:
        rows = [
            ("Initial Balance", f"${float(result.initial_balance):,.2f}"),
            ("Final Balance", f"${float(result.final_balance):,.2f}"),
            ("Total Return", f"${float(result.total_return):,.2f} ({float(result.total_return_pct):.2f}%)"),
            ("Max Drawdown", f"${float(result.max_drawdown):,.2f} ({float(result.max_drawdown_pct):.2f}%)"),
            ("Total Trades", str(result.total_trades)),
            ("Winning Trades", str(result.winning_trades)),
            ("Losing Trades", str(result.losing_trades)),
            ("Win Rate", f"{float(result.win_rate):.1f}%"),
            ("Avg Profit/Trade", f"${float(result.avg_profit_per_trade):,.4f}"),
            ("Buy Orders", str(result.total_buy_orders)),
            ("Sell Orders", str(result.total_sell_orders)),
        ]
        if result.sharpe_ratio is not None:
            rows.append(("Sharpe Ratio", f"{float(result.sharpe_ratio):.4f}"))

        table_rows = "\n".join(
            f"<tr><td>{html_mod.escape(k)}</td><td>{html_mod.escape(v)}</td></tr>"
            for k, v in rows
        )
        return f'<h2>Performance Metrics</h2><table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>{table_rows}</tbody></table>'

    def _equity_chart(self, result: BacktestResult) -> str:
        values = [e["portfolio_value"] for e in result.equity_curve]
        return (
            '<div class="chart">'
            + self.chart.line_chart(
                values,
                title="Equity Curve",
                y_label="Portfolio Value ($)",
                color="#2563eb",
                fill=True,
            )
            + "</div>"
        )

    def _drawdown_chart(self, result: BacktestResult) -> str:
        values = [e["portfolio_value"] for e in result.equity_curve]
        if not values:
            return ""
        peak = values[0]
        drawdowns = []
        for v in values:
            if v > peak:
                peak = v
            dd_pct = ((peak - v) / peak) * 100 if peak > 0 else 0
            drawdowns.append(-dd_pct)

        return (
            '<div class="chart">'
            + self.chart.line_chart(
                drawdowns,
                title="Drawdown (%)",
                y_label="Drawdown (%)",
                color="#dc2626",
                fill=True,
            )
            + "</div>"
        )

    def _trade_table(self, result: BacktestResult) -> str:
        history = result.trade_history[:self.config.max_trades_in_table]
        rows = []
        for t in history:
            rows.append(
                f"<tr><td>{html_mod.escape(str(t.get('timestamp', '')))}</td>"
                f"<td>{html_mod.escape(t.get('side', ''))}</td>"
                f"<td>${float(t.get('price', 0)):,.2f}</td>"
                f"<td>{float(t.get('amount', 0)):.6f}</td></tr>"
            )
        return (
            '<h2>Trade History</h2>'
            '<table><thead><tr><th>Time</th><th>Side</th><th>Price</th><th>Amount</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    def _comparison_summary(self, comparison: StrategyComparisonResult) -> str:
        rows = []
        for name, stats in comparison.summary.items():
            sharpe = f"{stats['sharpe_ratio']:.2f}" if stats.get("sharpe_ratio") is not None else "N/A"
            rows.append(
                f"<tr><td>{html_mod.escape(name)}</td>"
                f"<td>{stats['total_return_pct']:.2f}%</td>"
                f"<td>{stats['total_trades']}</td>"
                f"<td>{stats['win_rate']:.1f}%</td>"
                f"<td>{stats['max_drawdown_pct']:.2f}%</td>"
                f"<td>{sharpe}</td></tr>"
            )
        winner = comparison.get_winner("total_return_pct")
        winner_html = f'<p>Best Return: <strong>{html_mod.escape(winner or "N/A")}</strong></p>' if winner else ""

        return (
            '<h2>Strategy Comparison</h2>'
            + winner_html
            + '<table><thead><tr><th>Strategy</th><th>Return</th><th>Trades</th>'
            '<th>Win Rate</th><th>Max DD</th><th>Sharpe</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    def _rankings_table(self, comparison: StrategyComparisonResult) -> str:
        rows = []
        for metric, ranking in comparison.rankings.items():
            ranked = ", ".join(f"{i + 1}. {n}" for i, n in enumerate(ranking))
            rows.append(
                f"<tr><td>{html_mod.escape(metric)}</td><td>{html_mod.escape(ranked)}</td></tr>"
            )
        return (
            '<h2>Rankings</h2>'
            '<table><thead><tr><th>Metric</th><th>Ranking</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    def _distribution_chart(
        self, values: list[float], title: str = ""
    ) -> str:
        """Create a simple histogram approximation using bar chart."""
        n_bins = min(20, max(5, len(values) // 50))
        min_v = min(values)
        max_v = max(values)
        if min_v == max_v:
            return ""
        bin_w = (max_v - min_v) / n_bins

        bins = [0] * n_bins
        for v in values:
            idx = min(int((v - min_v) / bin_w), n_bins - 1)
            bins[idx] += 1

        labels = [f"{min_v + i * bin_w:.1f}" for i in range(n_bins)]
        return (
            '<div class="chart">'
            + self.chart.bar_chart(labels, [float(b) for b in bins], title=title, y_label="Count")
            + "</div>"
        )

    def _percentile_table(self, title: str, percentiles: dict[float, float]) -> str:
        rows = []
        for level, value in sorted(percentiles.items()):
            rows.append(f"<tr><td>{level:.0%}</td><td>{value:.2f}</td></tr>")
        return (
            f'<h3>{html_mod.escape(title)}</h3>'
            '<table><thead><tr><th>Percentile</th><th>Value</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    def _wrap_html(self, title: str, body: str) -> str:
        """Wrap content in a complete HTML document with CSS."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(title)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f8fafc; color: #1e293b; line-height: 1.6; padding: 2rem; max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 1.75rem; margin-bottom: 0.5rem; }}
  h2 {{ font-size: 1.25rem; margin: 1.5rem 0 0.75rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.25rem; }}
  h3 {{ font-size: 1.1rem; margin: 1rem 0 0.5rem; }}
  p {{ margin: 0.5rem 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 0.75rem 0; font-size: 0.9rem; }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }}
  th {{ background: #f1f5f9; font-weight: 600; }}
  tr:hover {{ background: #f8fafc; }}
  .summary {{ background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem; }}
  .stat-cards {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1rem; }}
  .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem 1rem; min-width: 120px; }}
  .card .label {{ display: block; font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card .value {{ display: block; font-size: 1.25rem; font-weight: 700; margin-top: 0.25rem; }}
  .positive {{ color: #16a34a; }}
  .negative {{ color: #dc2626; }}
  .chart {{ margin: 1.5rem 0; text-align: center; }}
  .metrics {{ background: white; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
  .badge-green {{ background: #16a34a; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }}
  .badge-red {{ background: #dc2626; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }}
  footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; font-size: 0.8rem; color: #94a3b8; text-align: center; }}
</style>
</head>
<body>
{body}
<footer>Generated by TRADERAGENT Backtest Report Generator | {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</footer>
</body>
</html>"""
