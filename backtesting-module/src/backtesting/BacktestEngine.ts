/**
 * Backtesting Engine
 * Runs historical simulations of trading strategies
 */

import type { Strategy } from '../trading/strategies/types.js';
import type { ExchangeInterface } from '../exchanges/ExchangeInterface.js';
import type { Candle } from '../exchanges/types.js';

export interface BacktestConfig {
  strategy: Strategy;
  symbol: string;
  startDate: Date;
  endDate: Date;
  initialCapital: number;
  commission: number; // 0.001 = 0.1%
  slippage: number; // 0.0005 = 0.05%
  timeframe: string;
}

export interface BacktestTrade {
  entryTime: Date;
  exitTime: Date;
  entryPrice: number;
  exitPrice: number;
  side: 'LONG' | 'SHORT';
  size: number;
  pnl: number;
  pnlPercent: number;
  commission: number;
  reason: string;
}

export interface BacktestMetrics {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  totalPnl: number;
  totalPnlPercent: number;
  maxDrawdown: number;
  sharpeRatio: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
  largestWin: number;
  largestLoss: number;
  expectancy: number;
  avgTrade: number;
}

export interface BacktestResult {
  trades: BacktestTrade[];
  metrics: BacktestMetrics;
  equity: Array<{ timestamp: Date; value: number }>;
}

interface Position {
  side: 'LONG' | 'SHORT';
  size: number;
  entryPrice: number;
  entryTime: Date;
  stopLoss?: number;
  takeProfit?: number;
}

/**
 * BacktestEngine - Executes historical backtests on trading strategies
 */
export class BacktestEngine {
  private exchange: ExchangeInterface;
  private config: BacktestConfig;
  private capital: number;
  private position: Position | null = null;
  private trades: BacktestTrade[] = [];
  private equity: Array<{ timestamp: Date; value: number }> = [];

  constructor(exchange: ExchangeInterface, config: BacktestConfig) {
    this.exchange = exchange;
    this.config = config;
    this.capital = config.initialCapital;
  }

  /**
   * Run the backtest simulation
   */
  async run(): Promise<BacktestResult> {
    console.log(`🔄 Starting backtest: ${this.config.symbol}`);
    console.log(
      `   Period: ${this.config.startDate.toISOString()} to ${this.config.endDate.toISOString()}`,
    );
    console.log(`   Initial capital: $${this.capital}`);

    // Fetch historical data
    const candles = await this.fetchHistoricalData();
    if (candles.length === 0) {
      throw new Error('No historical data available for backtesting');
    }

    console.log(`📊 Loaded ${candles.length} candles`);

    // Record initial equity
    this.equity.push({
      timestamp: new Date(candles[0].timestamp * 1000),
      value: this.capital,
    });

    // Run strategy on each candle (skip first 100 for indicator warmup)
    for (let i = 100; i < candles.length; i++) {
      const currentCandle = candles[i];
      const _historicalCandles = candles.slice(0, i + 1);

      // Convert candle to MarketData format
      const marketData = {
        symbol: this.config.symbol,
        timestamp: new Date(currentCandle.timestamp * 1000),
        price: currentCandle.close,
        volume: currentCandle.volume,
        ohlc: {
          open: currentCandle.open,
          high: currentCandle.high,
          low: currentCandle.low,
          close: currentCandle.close,
        },
      };

      // Get strategy decision (pass empty signals array for technical strategies)
      try {
        const decision = this.config.strategy.analyze(marketData, []);

        // Execute trades based on decision
        if (decision && !this.position) {
          // Open new position
          if (decision.direction === 'long') {
            this.openPosition('LONG', currentCandle, decision);
          } else if (decision.direction === 'short') {
            this.openPosition('SHORT', currentCandle, decision);
          }
        } else if (this.position) {
          // Check exit conditions
          const shouldExit = this.checkExitConditions(currentCandle, decision);
          if (shouldExit) {
            this.closePosition(currentCandle, shouldExit);
          }
        }
      } catch (error) {
        console.error(`Error analyzing candle ${i}:`, error);
      }

      // Record equity
      const currentEquity = this.calculateEquity(currentCandle);
      this.equity.push({
        timestamp: new Date(currentCandle.timestamp * 1000),
        value: currentEquity,
      });
    }

    // Close any open position at end
    if (this.position) {
      this.closePosition(candles[candles.length - 1], 'Backtest End');
    }

    console.log(`✅ Backtest complete: ${this.trades.length} trades executed`);
    console.log(`   Final capital: $${this.capital.toFixed(2)}`);
    console.log(`   Total P&L: $${(this.capital - this.config.initialCapital).toFixed(2)}`);

    return {
      trades: this.trades,
      metrics: this.calculateMetrics(),
      equity: this.equity,
    };
  }

  /**
   * Fetch historical candle data
   */
  private async fetchHistoricalData(): Promise<Candle[]> {
    const allCandles: Candle[] = [];
    const startTime = Math.floor(this.config.startDate.getTime() / 1000);
    const endTime = Math.floor(this.config.endDate.getTime() / 1000);
    let currentTime = startTime;

    // Fetch data in chunks (Bybit limit: 200 candles per request)
    while (currentTime < endTime) {
      try {
        const candles = await this.exchange.getCandles(
          this.config.symbol,
          this.config.timeframe,
          200,
          currentTime * 1000,
        );

        if (candles.length === 0) break;

        allCandles.push(...candles.filter((c) => c.timestamp <= endTime));

        // Move to next time window
        const lastCandle = candles[candles.length - 1];
        currentTime = lastCandle.timestamp + this.getTimeframeSeconds(this.config.timeframe);

        // Avoid rate limiting
        await new Promise((resolve) => setTimeout(resolve, 100));
      } catch (error) {
        console.error(`Failed to fetch candles at ${currentTime}:`, error);
        break;
      }
    }

    return allCandles;
  }

  /**
   * Open a new position
   */
  private openPosition(side: 'LONG' | 'SHORT', candle: Candle, decision: any): void {
    // Apply slippage
    const entryPrice =
      candle.close * (1 + (side === 'LONG' ? this.config.slippage : -this.config.slippage));

    // Calculate position size based on available capital and decision
    const positionSizePercent = decision.positionSize || 100; // Default 100%
    const size = (this.capital * (positionSizePercent / 100)) / entryPrice;

    this.position = {
      side,
      size,
      entryPrice,
      entryTime: new Date(candle.timestamp * 1000),
      stopLoss: decision.stopLoss,
      takeProfit: decision.takeProfit,
    };

    console.log(
      `📈 Opened ${side} position at $${entryPrice.toFixed(2)}, size: ${size.toFixed(6)}`,
    );
  }

  /**
   * Close the current position
   */
  private closePosition(candle: Candle, reason: string): void {
    if (!this.position) return;

    // Apply slippage
    const exitPrice =
      candle.close *
      (1 + (this.position.side === 'LONG' ? -this.config.slippage : this.config.slippage));

    // Calculate P&L
    const pnl =
      this.position.side === 'LONG'
        ? (exitPrice - this.position.entryPrice) * this.position.size
        : (this.position.entryPrice - exitPrice) * this.position.size;

    // Calculate commission (entry + exit)
    const commission =
      (this.position.entryPrice + exitPrice) * this.position.size * this.config.commission;

    const netPnl = pnl - commission;
    this.capital += netPnl;

    const trade: BacktestTrade = {
      entryTime: this.position.entryTime,
      exitTime: new Date(candle.timestamp * 1000),
      entryPrice: this.position.entryPrice,
      exitPrice,
      side: this.position.side,
      size: this.position.size,
      pnl: netPnl,
      pnlPercent: (netPnl / (this.position.entryPrice * this.position.size)) * 100,
      commission,
      reason,
    };

    this.trades.push(trade);

    console.log(
      `📉 Closed ${this.position.side} position at $${exitPrice.toFixed(2)}, P&L: $${netPnl.toFixed(2)} (${reason})`,
    );

    this.position = null;
  }

  /**
   * Check if position should be closed
   */
  private checkExitConditions(candle: Candle, decision: any): string | null {
    if (!this.position) return null;

    // Check stop loss
    if (this.position.stopLoss) {
      if (this.position.side === 'LONG' && candle.low <= this.position.stopLoss) {
        return 'Stop Loss';
      }
      if (this.position.side === 'SHORT' && candle.high >= this.position.stopLoss) {
        return 'Stop Loss';
      }
    }

    // Check take profit
    if (this.position.takeProfit) {
      if (this.position.side === 'LONG' && candle.high >= this.position.takeProfit) {
        return 'Take Profit';
      }
      if (this.position.side === 'SHORT' && candle.low <= this.position.takeProfit) {
        return 'Take Profit';
      }
    }

    // Check if strategy signals exit
    if (decision) {
      const shouldReverse =
        (this.position.side === 'LONG' && decision.direction === 'short') ||
        (this.position.side === 'SHORT' && decision.direction === 'long');

      if (shouldReverse) {
        return 'Strategy Signal';
      }
    }

    return null;
  }

  /**
   * Calculate current equity (capital + unrealized P&L)
   */
  private calculateEquity(candle: Candle): number {
    let equity = this.capital;

    if (this.position) {
      const currentPrice = candle.close;
      const pnl =
        this.position.side === 'LONG'
          ? (currentPrice - this.position.entryPrice) * this.position.size
          : (this.position.entryPrice - currentPrice) * this.position.size;
      equity += pnl;
    }

    return equity;
  }

  /**
   * Calculate backtest metrics
   */
  private calculateMetrics(): BacktestMetrics {
    if (this.trades.length === 0) {
      return {
        totalTrades: 0,
        winningTrades: 0,
        losingTrades: 0,
        winRate: 0,
        totalPnl: 0,
        totalPnlPercent: 0,
        maxDrawdown: 0,
        sharpeRatio: 0,
        profitFactor: 0,
        avgWin: 0,
        avgLoss: 0,
        largestWin: 0,
        largestLoss: 0,
        expectancy: 0,
        avgTrade: 0,
      };
    }

    const winningTrades = this.trades.filter((t) => t.pnl > 0);
    const losingTrades = this.trades.filter((t) => t.pnl <= 0);

    const totalPnl = this.trades.reduce((sum, t) => sum + t.pnl, 0);
    const totalWin = winningTrades.reduce((sum, t) => sum + t.pnl, 0);
    const totalLoss = Math.abs(losingTrades.reduce((sum, t) => sum + t.pnl, 0));

    // Calculate Sharpe ratio
    const returns = this.equity.map((e, i, arr) =>
      i === 0 ? 0 : (e.value - arr[i - 1].value) / arr[i - 1].value,
    );
    const avgReturn = returns.reduce((sum, r) => sum + r, 0) / returns.length;
    const stdDev = Math.sqrt(
      returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length,
    );
    const sharpeRatio = stdDev > 0 ? (avgReturn / stdDev) * Math.sqrt(252) : 0;

    // Calculate max drawdown
    let peak = this.config.initialCapital;
    let maxDrawdown = 0;
    for (const e of this.equity) {
      if (e.value > peak) peak = e.value;
      const drawdown = ((peak - e.value) / peak) * 100;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    }

    const avgTrade = totalPnl / this.trades.length;

    return {
      totalTrades: this.trades.length,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      winRate: (winningTrades.length / this.trades.length) * 100,
      totalPnl,
      totalPnlPercent: (totalPnl / this.config.initialCapital) * 100,
      maxDrawdown,
      sharpeRatio,
      profitFactor: totalLoss > 0 ? totalWin / totalLoss : totalWin > 0 ? Infinity : 0,
      avgWin: winningTrades.length > 0 ? totalWin / winningTrades.length : 0,
      avgLoss: losingTrades.length > 0 ? totalLoss / losingTrades.length : 0,
      largestWin: Math.max(...this.trades.map((t) => t.pnl), 0),
      largestLoss: Math.min(...this.trades.map((t) => t.pnl), 0),
      expectancy: avgTrade,
      avgTrade,
    };
  }

  /**
   * Get timeframe in seconds
   */
  private getTimeframeSeconds(timeframe: string): number {
    const map: Record<string, number> = {
      '1m': 60,
      '5m': 300,
      '15m': 900,
      '30m': 1800,
      '1h': 3600,
      '4h': 14400,
      '1d': 86400,
      '1w': 604800,
    };
    return map[timeframe] || 3600;
  }
}
