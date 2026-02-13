/**
 * Comparison Report Generator
 * Compares multiple backtest results side-by-side
 */

import { BacktestResults } from "../backtesting/BacktestRunner.js";
import { AdvancedMetrics } from "../backtesting/MetricsCalculator.js";
import * as fs from "fs";

export interface StrategyComparison {
  strategy: string;
  results: BacktestResults;
  metrics: AdvancedMetrics;
}

export interface ComparisonMetric {
  name: string;
  values: Array<{ strategy: string; value: number | string; isWinner?: boolean }>;
  format: "currency" | "percentage" | "number" | "ratio";
}

export class ComparisonReportGenerator {
  /**
   * Generate HTML comparison report
   */
  static generateHTML(
    comparisons: StrategyComparison[],
    outputPath: string
  ): void {
    const html = this.createComparisonHTML(comparisons);
    fs.writeFileSync(outputPath, html);
    console.log(`📊 Comparison HTML report saved: ${outputPath}`);
  }

  /**
   * Generate CSV comparison report
   */
  static generateCSV(
    comparisons: StrategyComparison[],
    outputPath: string
  ): void {
    const metrics = this.extractMetrics(comparisons);

    const header = ["Metric", ...comparisons.map((c) => c.strategy)];
    const rows = metrics.map((metric) => [
      metric.name,
      ...metric.values.map((v) => {
        const winner = v.isWinner ? " 🏆" : "";
        return `${v.value}${winner}`;
      }),
    ]);

    const csv = [header, ...rows].map((row) => row.join(",")).join("\n");
    fs.writeFileSync(outputPath, csv);
    console.log(`📊 Comparison CSV report saved: ${outputPath}`);
  }

  /**
   * Extract and compare metrics
   */
  private static extractMetrics(
    comparisons: StrategyComparison[]
  ): ComparisonMetric[] {
    const metrics: ComparisonMetric[] = [
      {
        name: "Total Return %",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.results.totalReturnPct.toFixed(2) + "%",
        })),
        format: "percentage",
      },
      {
        name: "Final Balance",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: "$" + c.results.finalBalance.toLocaleString(),
        })),
        format: "currency",
      },
      {
        name: "Sharpe Ratio",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.metrics.sharpeRatio.toFixed(2),
        })),
        format: "ratio",
      },
      {
        name: "Sortino Ratio",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.metrics.sortinoRatio.toFixed(2),
        })),
        format: "ratio",
      },
      {
        name: "Max Drawdown %",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.metrics.maxDrawdownPct.toFixed(2) + "%",
        })),
        format: "percentage",
      },
      {
        name: "Profit Factor",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.results.profitFactor.toFixed(2),
        })),
        format: "ratio",
      },
      {
        name: "Win Rate %",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.results.winRate.toFixed(1) + "%",
        })),
        format: "percentage",
      },
      {
        name: "Total Trades",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.results.totalTrades.toString(),
        })),
        format: "number",
      },
      {
        name: "Calmar Ratio",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.metrics.calmarRatio.toFixed(2),
        })),
        format: "ratio",
      },
      {
        name: "Recovery Factor",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.metrics.recoveryFactor.toFixed(2),
        })),
        format: "ratio",
      },
      {
        name: "Volatility",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: (c.metrics.volatility * 100).toFixed(2) + "%",
        })),
        format: "percentage",
      },
      {
        name: "Avg Trade Duration (hours)",
        values: comparisons.map((c) => ({
          strategy: c.strategy,
          value: c.metrics.averageTradeDuration.toFixed(1),
        })),
        format: "number",
      },
    ];

    // Mark winners (higher is better, except Max Drawdown)
    metrics.forEach((metric) => {
      const numericValues = metric.values.map((v) => {
        const str = v.value.toString().replace(/[^0-9.-]/g, "");
        return parseFloat(str);
      });

      const isLowerBetter = metric.name.includes("Drawdown");
      const bestValue = isLowerBetter
        ? Math.min(...numericValues)
        : Math.max(...numericValues);

      metric.values.forEach((v, i) => {
        v.isWinner = numericValues[i] === bestValue;
      });
    });

    return metrics;
  }

  /**
   * Create HTML comparison report
   */
  private static createComparisonHTML(
    comparisons: StrategyComparison[]
  ): string {
    const metrics = this.extractMetrics(comparisons);

    return `<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strategy Comparison Report</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .section {
            padding: 40px;
        }

        .section h2 {
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }

        table th {
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }

        table th:first-child {
            text-align: left;
            min-width: 250px;
        }

        table td {
            padding: 15px;
            border-bottom: 1px solid #e5e7eb;
        }

        table tr:hover {
            background: #f3f4f6;
        }

        .winner {
            background: #d1fae5 !important;
            font-weight: bold;
            position: relative;
        }

        .winner::after {
            content: "🏆";
            margin-left: 8px;
        }

        .metric-name {
            font-weight: 600;
            color: #4b5563;
        }

        .positive {
            color: #10b981;
        }

        .negative {
            color: #ef4444;
        }

        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .summary-card {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }

        .summary-card h3 {
            font-size: 1.2em;
            color: #667eea;
            margin-bottom: 15px;
        }

        .summary-card .stat {
            margin: 8px 0;
            display: flex;
            justify-content: space-between;
        }

        .summary-card .label {
            color: #666;
        }

        .summary-card .value {
            font-weight: bold;
            color: #333;
        }

        .footer {
            padding: 20px;
            text-align: center;
            background: #f8f9fa;
            color: #666;
        }

        @media (max-width: 768px) {
            table {
                font-size: 0.9em;
            }

            .summary-cards {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Strategy Comparison Report</h1>
            <div class="subtitle">Comparing ${comparisons.length} Trading Strategies</div>
            <div class="subtitle">${new Date().toLocaleString()}</div>
        </div>

        <div class="section">
            <h2>📈 Strategy Overview</h2>
            <div class="summary-cards">
                ${comparisons.map((c) => this.createSummaryCard(c)).join("")}
            </div>
        </div>

        <div class="section">
            <h2>🔍 Detailed Comparison</h2>
            ${this.createComparisonTable(comparisons, metrics)}
        </div>

        <div class="footer">
            <p>Generated by TRADERAGENT Backtest Module • ${new Date().toLocaleString()}</p>
            <p>🤖 Powered by Claude Code</p>
        </div>
    </div>
</body>
</html>`;
  }

  private static createSummaryCard(comparison: StrategyComparison): string {
    const { strategy, results, metrics } = comparison;
    const isProfit = results.totalReturn > 0;

    return `
            <div class="summary-card">
                <h3>${strategy}</h3>
                <div class="stat">
                    <span class="label">Return:</span>
                    <span class="value ${isProfit ? "positive" : "negative"}">
                        ${results.totalReturnPct >= 0 ? "+" : ""}${results.totalReturnPct.toFixed(2)}%
                    </span>
                </div>
                <div class="stat">
                    <span class="label">Sharpe:</span>
                    <span class="value">${metrics.sharpeRatio.toFixed(2)}</span>
                </div>
                <div class="stat">
                    <span class="label">Max DD:</span>
                    <span class="value negative">${metrics.maxDrawdownPct.toFixed(2)}%</span>
                </div>
                <div class="stat">
                    <span class="label">Win Rate:</span>
                    <span class="value">${results.winRate.toFixed(1)}%</span>
                </div>
                <div class="stat">
                    <span class="label">Trades:</span>
                    <span class="value">${results.totalTrades}</span>
                </div>
            </div>`;
  }

  private static createComparisonTable(
    comparisons: StrategyComparison[],
    metrics: ComparisonMetric[]
  ): string {
    const headers = ["Metric", ...comparisons.map((c) => c.strategy)];

    const rows = metrics.map((metric) => {
      const cells = metric.values.map((v) => {
        const className = v.isWinner ? "winner" : "";
        return `<td class="${className}">${v.value}</td>`;
      });

      return `
            <tr>
                <td class="metric-name">${metric.name}</td>
                ${cells.join("")}
            </tr>`;
    });

    return `
        <table>
            <thead>
                <tr>
                    ${headers.map((h) => `<th>${h}</th>`).join("")}
                </tr>
            </thead>
            <tbody>
                ${rows.join("")}
            </tbody>
        </table>`;
  }
}
