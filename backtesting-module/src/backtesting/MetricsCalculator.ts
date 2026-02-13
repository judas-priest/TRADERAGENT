/**
 * Metrics Calculator
 * Calculates advanced trading metrics (Sharpe, Drawdown, etc.)
 */

import { Trade } from "../strategies/IStrategy.js";
import { BacktestResults } from "./BacktestRunner.js";

export interface AdvancedMetrics {
  sharpeRatio: number;
  sortinoRatio: number;
  maxDrawdown: number;
  maxDrawdownPct: number;
  maxDrawdownDuration: number; // in days
  calmarRatio: number;
  recoveryFactor: number;
  volatility: number;
  averageTradeDuration: number; // in hours
}

export class MetricsCalculator {
  /**
   * Calculate Sharpe Ratio
   * Risk-adjusted return metric
   */
  static calculateSharpeRatio(
    returns: number[],
    riskFreeRate: number = 0
  ): number {
    if (returns.length === 0) return 0;

    const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
    const excessReturn = avgReturn - riskFreeRate;

    const variance =
      returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) /
      returns.length;
    const stdDev = Math.sqrt(variance);

    if (stdDev === 0) return 0;

    // Annualized Sharpe (assuming daily returns)
    return (excessReturn / stdDev) * Math.sqrt(365);
  }

  /**
   * Calculate Sortino Ratio
   * Like Sharpe but only penalizes downside volatility
   */
  static calculateSortinoRatio(
    returns: number[],
    riskFreeRate: number = 0
  ): number {
    if (returns.length === 0) return 0;

    const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
    const excessReturn = avgReturn - riskFreeRate;

    // Only negative returns for downside deviation
    const negativeReturns = returns.filter((r) => r < 0);
    if (negativeReturns.length === 0) return 999; // No downside!

    const downsideVariance =
      negativeReturns.reduce((sum, r) => sum + Math.pow(r, 2), 0) /
      returns.length;
    const downsideStdDev = Math.sqrt(downsideVariance);

    if (downsideStdDev === 0) return 0;

    return (excessReturn / downsideStdDev) * Math.sqrt(365);
  }

  /**
   * Calculate Maximum Drawdown
   * Returns both absolute and percentage drawdown
   */
  static calculateMaxDrawdown(equityCurve: Array<{ timestamp: number; balance: number }>): {
    max: number;
    maxPct: number;
    duration: number;
  } {
    if (equityCurve.length === 0) {
      return { max: 0, maxPct: 0, duration: 0 };
    }

    let maxDrawdown = 0;
    let maxDrawdownPct = 0;
    let maxDuration = 0;

    let peak = equityCurve[0].balance;
    let peakTime = equityCurve[0].timestamp;
    let drawdownStart = 0;

    for (let i = 0; i < equityCurve.length; i++) {
      const balance = equityCurve[i].balance;

      if (balance > peak) {
        peak = balance;
        peakTime = equityCurve[i].timestamp;
      } else {
        const drawdown = peak - balance;
        const drawdownPct = (drawdown / peak) * 100;

        if (drawdown > maxDrawdown) {
          maxDrawdown = drawdown;
          maxDrawdownPct = drawdownPct;
          drawdownStart = peakTime;
        }

        // Duration of current drawdown
        const duration =
          (equityCurve[i].timestamp - drawdownStart) / (1000 * 60 * 60 * 24);
        if (duration > maxDuration) {
          maxDuration = duration;
        }
      }
    }

    return {
      max: maxDrawdown,
      maxPct: maxDrawdownPct,
      duration: maxDuration,
    };
  }

  /**
   * Calculate Profit Factor
   */
  static calculateProfitFactor(trades: Trade[]): number {
    const wins = trades.filter((t) => t.pnl > 0);
    const losses = trades.filter((t) => t.pnl <= 0);

    const grossProfit = wins.reduce((sum, t) => sum + t.pnl, 0);
    const grossLoss = Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0));

    if (grossLoss === 0) return grossProfit > 0 ? 999 : 0;

    return grossProfit / grossLoss;
  }

  /**
   * Calculate Win Rate
   */
  static calculateWinRate(trades: Trade[]): number {
    if (trades.length === 0) return 0;
    const wins = trades.filter((t) => t.pnl > 0).length;
    return (wins / trades.length) * 100;
  }

  /**
   * Calculate Calmar Ratio
   * Annual return / Max Drawdown
   */
  static calculateCalmarRatio(
    annualReturn: number,
    maxDrawdownPct: number
  ): number {
    if (maxDrawdownPct === 0) return 0;
    return annualReturn / maxDrawdownPct;
  }

  /**
   * Calculate Recovery Factor
   * Net Profit / Max Drawdown
   */
  static calculateRecoveryFactor(
    netProfit: number,
    maxDrawdown: number
  ): number {
    if (maxDrawdown === 0) return 0;
    return netProfit / maxDrawdown;
  }

  /**
   * Calculate returns volatility (standard deviation)
   */
  static calculateVolatility(returns: number[]): number {
    if (returns.length === 0) return 0;

    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const variance =
      returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) /
      returns.length;

    return Math.sqrt(variance) * Math.sqrt(365); // Annualized
  }

  /**
   * Calculate average trade duration
   */
  static calculateAverageTradeDuration(trades: Trade[]): number {
    if (trades.length === 0) return 0;

    const totalDuration = trades.reduce((sum, t) => sum + t.duration, 0);
    return totalDuration / trades.length / (1000 * 60 * 60); // Convert to hours
  }

  /**
   * Calculate all advanced metrics from backtest results
   */
  static calculateAdvancedMetrics(
    results: BacktestResults
  ): AdvancedMetrics {
    // Calculate daily returns from equity curve
    const returns: number[] = [];
    for (let i = 1; i < results.equityCurve.length; i++) {
      const prev = results.equityCurve[i - 1].balance;
      const current = results.equityCurve[i].balance;
      returns.push((current - prev) / prev);
    }

    const drawdown = this.calculateMaxDrawdown(results.equityCurve);

    // Annualized return
    const totalDays =
      (new Date(results.period.end).getTime() -
        new Date(results.period.start).getTime()) /
      (1000 * 60 * 60 * 24);
    const annualizedReturn =
      (results.totalReturnPct / 100) * (365 / totalDays) * 100;

    return {
      sharpeRatio: this.calculateSharpeRatio(returns),
      sortinoRatio: this.calculateSortinoRatio(returns),
      maxDrawdown: drawdown.max,
      maxDrawdownPct: drawdown.maxPct,
      maxDrawdownDuration: drawdown.duration,
      calmarRatio: this.calculateCalmarRatio(
        annualizedReturn,
        drawdown.maxPct
      ),
      recoveryFactor: this.calculateRecoveryFactor(
        results.netProfit,
        drawdown.max
      ),
      volatility: this.calculateVolatility(returns),
      averageTradeDuration: this.calculateAverageTradeDuration(results.trades),
    };
  }
}
