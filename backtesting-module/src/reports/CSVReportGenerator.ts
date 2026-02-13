/**
 * CSV Report Generator
 * Exports backtest results to CSV format
 */

import { BacktestResults } from "../backtesting/BacktestRunner.js";
import { AdvancedMetrics } from "../backtesting/MetricsCalculator.js";
import * as fs from "fs";

export class CSVReportGenerator {
  /**
   * Generate summary CSV
   */
  static generateSummary(
    results: BacktestResults,
    metrics: AdvancedMetrics,
    outputPath: string
  ): void {
    const rows = [
      ["Metric", "Value"],
      ["Strategy", results.strategy],
      ["Symbol", results.symbol],
      ["Timeframe", results.timeframe],
      ["Period Start", results.period.start],
      ["Period End", results.period.end],
      [""],
      ["Initial Balance", results.initialBalance.toString()],
      ["Final Balance", results.finalBalance.toString()],
      ["Total Return", results.totalReturn.toString()],
      ["Total Return %", results.totalReturnPct.toString()],
      [""],
      ["Total Trades", results.totalTrades.toString()],
      ["Winning Trades", results.winningTrades.toString()],
      ["Losing Trades", results.losingTrades.toString()],
      ["Win Rate %", results.winRate.toString()],
      [""],
      ["Gross Profit", results.grossProfit.toString()],
      ["Gross Loss", results.grossLoss.toString()],
      ["Net Profit", results.netProfit.toString()],
      ["Profit Factor", results.profitFactor.toString()],
      ["Average Win", results.averageWin.toString()],
      ["Average Loss", results.averageLoss.toString()],
      ["Largest Win", results.largestWin.toString()],
      ["Largest Loss", results.largestLoss.toString()],
      [""],
      ["Sharpe Ratio", metrics.sharpeRatio.toString()],
      ["Sortino Ratio", metrics.sortinoRatio.toString()],
      ["Max Drawdown", metrics.maxDrawdown.toString()],
      ["Max Drawdown %", metrics.maxDrawdownPct.toString()],
      ["Calmar Ratio", metrics.calmarRatio.toString()],
      ["Recovery Factor", metrics.recoveryFactor.toString()],
      ["Volatility", metrics.volatility.toString()],
      ["Avg Trade Duration (hours)", metrics.averageTradeDuration.toString()],
    ];

    const csv = rows.map((row) => row.join(",")).join("\n");
    fs.writeFileSync(outputPath, csv);
    console.log(`📄 Summary CSV saved: ${outputPath}`);
  }

  /**
   * Generate trades CSV
   */
  static generateTrades(results: BacktestResults, outputPath: string): void {
    const header = [
      "ID",
      "Type",
      "Entry Price",
      "Exit Price",
      "Entry Time",
      "Exit Time",
      "Size",
      "P&L",
      "P&L %",
      "Duration (hours)",
      "Stop Loss",
      "Take Profit",
      "Exit Reason",
    ];

    const rows = results.trades.map((trade) => [
      trade.id,
      trade.type,
      trade.entryPrice.toString(),
      trade.exitPrice.toString(),
      new Date(trade.entryTime).toISOString(),
      new Date(trade.exitTime).toISOString(),
      trade.size.toString(),
      trade.pnl.toString(),
      trade.pnlPct.toString(),
      (trade.duration / (1000 * 60 * 60)).toFixed(2),
      trade.stopLoss?.toString() || "",
      trade.takeProfit?.toString() || "",
      trade.exitReason,
    ]);

    const csv = [header, ...rows].map((row) => row.join(",")).join("\n");
    fs.writeFileSync(outputPath, csv);
    console.log(`📄 Trades CSV saved: ${outputPath}`);
  }

  /**
   * Generate equity curve CSV
   */
  static generateEquity(results: BacktestResults, outputPath: string): void {
    const header = ["Timestamp", "DateTime", "Balance"];

    const rows = results.equityCurve.map((point) => [
      point.timestamp.toString(),
      new Date(point.timestamp).toISOString(),
      point.balance.toString(),
    ]);

    const csv = [header, ...rows].map((row) => row.join(",")).join("\n");
    fs.writeFileSync(outputPath, csv);
    console.log(`📄 Equity CSV saved: ${outputPath}`);
  }

  /**
   * Generate all CSV reports
   */
  static generateAll(
    results: BacktestResults,
    metrics: AdvancedMetrics,
    baseDir: string
  ): void {
    this.generateSummary(results, metrics, `${baseDir}/summary.csv`);
    this.generateTrades(results, `${baseDir}/trades.csv`);
    this.generateEquity(results, `${baseDir}/equity.csv`);
  }
}
