/**
 * HTML Report Generator
 * Generates beautiful HTML reports from backtest results
 */

import { BacktestResults } from "../backtesting/BacktestRunner.js";
import { AdvancedMetrics } from "../backtesting/MetricsCalculator.js";
import * as fs from "fs";

export class HTMLReportGenerator {
  static generate(
    results: BacktestResults,
    metrics: AdvancedMetrics,
    outputPath: string
  ): void {
    const html = this.createHTML(results, metrics);
    fs.writeFileSync(outputPath, html);
    console.log(`📄 HTML report saved: ${outputPath}`);
  }

  private static createHTML(
    results: BacktestResults,
    metrics: AdvancedMetrics
  ): string {
    return `<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Report - ${results.strategy}</title>
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
            max-width: 1200px;
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

        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 40px;
            background: #f8f9fa;
        }

        .metric-card {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }

        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .metric-card .label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 8px;
        }

        .metric-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }

        .metric-card .value.positive {
            color: #10b981;
        }

        .metric-card .value.negative {
            color: #ef4444;
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
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }

        table td {
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }

        table tr:hover {
            background: #f3f4f6;
        }

        .trade-row.win {
            background: #d1fae5;
        }

        .trade-row.loss {
            background: #fee2e2;
        }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }

        .badge.win {
            background: #10b981;
            color: white;
        }

        .badge.loss {
            background: #ef4444;
            color: white;
        }

        .footer {
            padding: 20px;
            text-align: center;
            background: #f8f9fa;
            color: #666;
        }

        @media (max-width: 768px) {
            .summary {
                grid-template-columns: 1fr;
            }

            table {
                font-size: 0.9em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Backtest Report</h1>
            <div class="subtitle">${results.strategy}</div>
            <div class="subtitle">${results.symbol} • ${results.timeframe}</div>
            <div class="subtitle">${results.period.start} → ${results.period.end}</div>
        </div>

        <div class="summary">
            ${this.createMetricCard(
              "Начальный баланс",
              `$${results.initialBalance.toLocaleString()}`
            )}
            ${this.createMetricCard(
              "Конечный баланс",
              `$${results.finalBalance.toLocaleString()}`,
              results.totalReturn > 0 ? "positive" : "negative"
            )}
            ${this.createMetricCard(
              "Общая доходность",
              `${results.totalReturnPct >= 0 ? "+" : ""}${results.totalReturnPct.toFixed(2)}%`,
              results.totalReturn > 0 ? "positive" : "negative"
            )}
            ${this.createMetricCard(
              "Всего сделок",
              results.totalTrades.toString()
            )}
            ${this.createMetricCard(
              "Win Rate",
              `${results.winRate.toFixed(1)}%`,
              results.winRate > 50 ? "positive" : "negative"
            )}
            ${this.createMetricCard(
              "Profit Factor",
              results.profitFactor.toFixed(2),
              results.profitFactor > 1 ? "positive" : "negative"
            )}
        </div>

        <div class="section">
            <h2>📊 Детальные метрики</h2>
            ${this.createMetricsTable(results, metrics)}
        </div>

        <div class="section">
            <h2>💼 История сделок</h2>
            ${this.createTradesTable(results)}
        </div>

        <div class="footer">
            <p>Generated by TRADERAGENT Backtest Module • ${new Date().toLocaleString()}</p>
            <p>🤖 Powered by Claude Code</p>
        </div>
    </div>
</body>
</html>`;
  }

  private static createMetricCard(
    label: string,
    value: string,
    className: string = ""
  ): string {
    return `
            <div class="metric-card">
                <div class="label">${label}</div>
                <div class="value ${className}">${value}</div>
            </div>`;
  }

  private static createMetricsTable(
    results: BacktestResults,
    metrics: AdvancedMetrics
  ): string {
    return `
        <table>
            <tr>
                <th>Метрика</th>
                <th>Значение</th>
            </tr>
            <tr>
                <td>Прибыльные сделки</td>
                <td>${results.winningTrades}</td>
            </tr>
            <tr>
                <td>Убыточные сделки</td>
                <td>${results.losingTrades}</td>
            </tr>
            <tr>
                <td>Средняя прибыль</td>
                <td>$${results.averageWin.toFixed(2)}</td>
            </tr>
            <tr>
                <td>Средний убыток</td>
                <td>$${results.averageLoss.toFixed(2)}</td>
            </tr>
            <tr>
                <td>Наибольшая прибыль</td>
                <td>$${results.largestWin.toFixed(2)}</td>
            </tr>
            <tr>
                <td>Наибольший убыток</td>
                <td>$${results.largestLoss.toFixed(2)}</td>
            </tr>
            <tr>
                <td><strong>Sharpe Ratio</strong></td>
                <td><strong>${metrics.sharpeRatio.toFixed(2)}</strong></td>
            </tr>
            <tr>
                <td><strong>Sortino Ratio</strong></td>
                <td><strong>${metrics.sortinoRatio.toFixed(2)}</strong></td>
            </tr>
            <tr>
                <td><strong>Max Drawdown</strong></td>
                <td><strong>${metrics.maxDrawdownPct.toFixed(2)}%</strong></td>
            </tr>
            <tr>
                <td>Calmar Ratio</td>
                <td>${metrics.calmarRatio.toFixed(2)}</td>
            </tr>
            <tr>
                <td>Recovery Factor</td>
                <td>${metrics.recoveryFactor.toFixed(2)}</td>
            </tr>
            <tr>
                <td>Волатильность</td>
                <td>${(metrics.volatility * 100).toFixed(2)}%</td>
            </tr>
            <tr>
                <td>Средняя длительность сделки</td>
                <td>${metrics.averageTradeDuration.toFixed(1)} часов</td>
            </tr>
        </table>`;
  }

  private static createTradesTable(results: BacktestResults): string {
    const tradesHTML = results.trades
      .slice(0, 50) // First 50 trades
      .map((trade) => {
        const isWin = trade.pnl > 0;
        const rowClass = isWin ? "win" : "loss";
        const badgeClass = isWin ? "win" : "loss";

        return `
            <tr class="trade-row ${rowClass}">
                <td>${trade.id}</td>
                <td><span class="badge ${badgeClass}">${trade.type}</span></td>
                <td>$${trade.entryPrice.toFixed(2)}</td>
                <td>$${trade.exitPrice.toFixed(2)}</td>
                <td>${isWin ? "+" : ""}$${trade.pnl.toFixed(2)}</td>
                <td>${isWin ? "+" : ""}${trade.pnlPct.toFixed(2)}%</td>
                <td>${trade.exitReason}</td>
                <td>${new Date(trade.entryTime).toLocaleDateString()}</td>
            </tr>`;
      })
      .join("");

    return `
        <table>
            <tr>
                <th>ID</th>
                <th>Тип</th>
                <th>Вход</th>
                <th>Выход</th>
                <th>P&L</th>
                <th>P&L %</th>
                <th>Причина</th>
                <th>Дата</th>
            </tr>
            ${tradesHTML}
        </table>
        ${
          results.trades.length > 50
            ? `<p style="margin-top: 20px; color: #666;">Показаны первые 50 из ${results.trades.length} сделок</p>`
            : ""
        }`;
  }
}
