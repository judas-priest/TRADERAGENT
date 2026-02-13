/**
 * Backtest Runner
 * Runs complete backtests with position management and metrics
 */

import { Candle } from "../adapters/CSVDataLoader.js";
import {
  IStrategy,
  Signal,
  Position,
  Trade,
  MarketContext,
} from "../strategies/IStrategy.js";

export interface BacktestConfig {
  initialBalance: number;
  commission: number; // 0.001 = 0.1%
  slippage: number; // 0.0005 = 0.05%
  positionSize: number; // % of balance per trade (0.1 = 10%)
  maxOpenPositions: number;
}

export interface BacktestResults {
  // Basic info
  strategy: string;
  symbol: string;
  timeframe: string;
  period: { start: string; end: string };

  // Performance
  initialBalance: number;
  finalBalance: number;
  totalReturn: number;
  totalReturnPct: number;

  // Trades
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;

  // P&L
  grossProfit: number;
  grossLoss: number;
  netProfit: number;
  profitFactor: number;
  averageWin: number;
  averageLoss: number;
  largestWin: number;
  largestLoss: number;

  // All trades
  trades: Trade[];

  // Equity curve
  equityCurve: Array<{ timestamp: number; balance: number }>;
}

const DEFAULT_CONFIG: BacktestConfig = {
  initialBalance: 10000,
  commission: 0.001, // 0.1%
  slippage: 0.0005, // 0.05%
  positionSize: 0.1, // 10% per trade
  maxOpenPositions: 1,
};

export class BacktestRunner {
  private config: BacktestConfig;
  private balance: number;
  private openPositions: Map<string, Position> = new Map();
  private closedTrades: Trade[] = [];
  private equityCurve: Array<{ timestamp: number; balance: number }> = [];
  private tradeIdCounter = 0;

  constructor(config: Partial<BacktestConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.balance = this.config.initialBalance;
  }

  async run(
    strategy: IStrategy,
    candles: Candle[],
    symbol: string,
    timeframe: string
  ): Promise<BacktestResults> {
    console.log(`\n🚀 Running backtest: ${strategy.name}`);
    console.log(`   Symbol: ${symbol}, Timeframe: ${timeframe}`);
    console.log(`   Candles: ${candles.length}, Initial Balance: $${this.balance}`);

    // Reset state
    this.reset();
    strategy.reset();

    // Simulate through all candles
    for (let i = 0; i < candles.length; i++) {
      const candle = candles[i];

      // Check open positions for SL/TP
      this.checkPositions(candle);

      // Get signal from strategy
      const context: MarketContext = {
        candles,
        currentIndex: i,
        balance: this.balance,
        openPosition: this.openPositions.size > 0
          ? Array.from(this.openPositions.values())[0]
          : undefined,
      };

      const signal = strategy.analyze(candle, context);

      // Execute signal
      if (signal) {
        this.executeSignal(signal, candle, strategy);
      }

      // Record equity
      if (i % 24 === 0) {
        // Record every 24 candles
        this.equityCurve.push({
          timestamp: candle.timestamp,
          balance: this.getEquity(candle.close),
        });
      }
    }

    // Close any remaining positions
    const lastCandle = candles[candles.length - 1];
    this.closeAllPositions(lastCandle, "END");

    // Calculate results
    return this.calculateResults(strategy.name, symbol, timeframe, candles);
  }

  private reset() {
    this.balance = this.config.initialBalance;
    this.openPositions.clear();
    this.closedTrades = [];
    this.equityCurve = [];
    this.tradeIdCounter = 0;
  }

  private executeSignal(signal: Signal, candle: Candle, strategy: IStrategy) {
    if (this.openPositions.size >= this.config.maxOpenPositions) {
      return;
    }

    if (signal.type === "CLOSE" && this.openPositions.size > 0) {
      // Close existing position
      const position = Array.from(this.openPositions.values())[0];
      this.closePosition(position, candle, "SIGNAL");
      return;
    }

    if (signal.type === "BUY" || signal.type === "SELL") {
      this.openPosition(signal, candle, strategy);
    }
  }

  private openPosition(signal: Signal, candle: Candle, strategy: IStrategy) {
    // Calculate position size
    const positionValue = this.balance * this.config.positionSize;
    const entryPrice = this.applySlippage(signal.price, signal.type);
    const size = positionValue / entryPrice;

    // Apply commission
    const commission = positionValue * this.config.commission;
    this.balance -= commission;

    const position: Position = {
      id: `trade_${++this.tradeIdCounter}`,
      type: signal.type === "BUY" ? "LONG" : "SHORT",
      entryPrice,
      entryTime: candle.timestamp,
      size,
      stopLoss: signal.stopLoss,
      takeProfit: signal.takeProfit,
      currentPrice: entryPrice,
      unrealizedPnL: 0,
    };

    this.openPositions.set(position.id, position);
    strategy.onTradeOpen?.(position);

    console.log(
      `   📈 ${position.type} position opened: $${entryPrice.toFixed(2)} (size: ${size.toFixed(4)})`
    );
  }

  private checkPositions(candle: Candle) {
    for (const [id, position] of this.openPositions) {
      position.currentPrice = candle.close;

      // Calculate unrealized P&L
      if (position.type === "LONG") {
        position.unrealizedPnL = (candle.close - position.entryPrice) * position.size;
      } else {
        position.unrealizedPnL = (position.entryPrice - candle.close) * position.size;
      }

      // Check Stop Loss
      if (position.stopLoss) {
        const slHit =
          position.type === "LONG"
            ? candle.low <= position.stopLoss
            : candle.high >= position.stopLoss;

        if (slHit) {
          this.closePosition(position, candle, "SL");
          continue;
        }
      }

      // Check Take Profit
      if (position.takeProfit) {
        const tpHit =
          position.type === "LONG"
            ? candle.high >= position.takeProfit
            : candle.low <= position.takeProfit;

        if (tpHit) {
          this.closePosition(position, candle, "TP");
        }
      }
    }
  }

  private closePosition(
    position: Position,
    candle: Candle,
    reason: "TP" | "SL" | "SIGNAL" | "END"
  ) {
    let exitPrice: number;

    if (reason === "TP" && position.takeProfit) {
      exitPrice = position.takeProfit;
    } else if (reason === "SL" && position.stopLoss) {
      exitPrice = position.stopLoss;
    } else {
      exitPrice = candle.close;
    }

    // Calculate P&L
    let pnl: number;
    if (position.type === "LONG") {
      pnl = (exitPrice - position.entryPrice) * position.size;
    } else {
      pnl = (position.entryPrice - exitPrice) * position.size;
    }

    // Apply commission
    const positionValue = exitPrice * position.size;
    const commission = positionValue * this.config.commission;
    pnl -= commission;

    // Update balance
    this.balance += pnl + position.entryPrice * position.size;

    const trade: Trade = {
      id: position.id,
      type: position.type,
      entryPrice: position.entryPrice,
      entryTime: position.entryTime,
      exitPrice,
      exitTime: candle.timestamp,
      size: position.size,
      pnl,
      pnlPct: (pnl / (position.entryPrice * position.size)) * 100,
      duration: candle.timestamp - position.entryTime,
      stopLoss: position.stopLoss,
      takeProfit: position.takeProfit,
      exitReason: reason,
    };

    this.closedTrades.push(trade);
    this.openPositions.delete(position.id);

    const emoji = pnl > 0 ? "✅" : "❌";
    console.log(
      `   ${emoji} Position closed (${reason}): ${pnl > 0 ? "+" : ""}$${pnl.toFixed(2)} (${trade.pnlPct.toFixed(2)}%)`
    );
  }

  private closeAllPositions(candle: Candle, reason: "END") {
    for (const position of this.openPositions.values()) {
      this.closePosition(position, candle, reason);
    }
  }

  private applySlippage(price: number, type: "BUY" | "SELL"): number {
    const slippage = price * this.config.slippage;
    return type === "BUY" ? price + slippage : price - slippage;
  }

  private getEquity(currentPrice: number): number {
    let equity = this.balance;

    for (const position of this.openPositions.values()) {
      const positionValue = currentPrice * position.size;
      equity += positionValue;
    }

    return equity;
  }

  private calculateResults(
    strategyName: string,
    symbol: string,
    timeframe: string,
    candles: Candle[]
  ): BacktestResults {
    const trades = this.closedTrades;
    const winningTrades = trades.filter((t) => t.pnl > 0);
    const losingTrades = trades.filter((t) => t.pnl <= 0);

    const grossProfit = winningTrades.reduce((sum, t) => sum + t.pnl, 0);
    const grossLoss = Math.abs(losingTrades.reduce((sum, t) => sum + t.pnl, 0));
    const netProfit = this.balance - this.config.initialBalance;

    return {
      strategy: strategyName,
      symbol,
      timeframe,
      period: {
        start: candles[0].datetime,
        end: candles[candles.length - 1].datetime,
      },

      initialBalance: this.config.initialBalance,
      finalBalance: this.balance,
      totalReturn: netProfit,
      totalReturnPct: (netProfit / this.config.initialBalance) * 100,

      totalTrades: trades.length,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      winRate: trades.length > 0 ? (winningTrades.length / trades.length) * 100 : 0,

      grossProfit,
      grossLoss,
      netProfit,
      profitFactor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 999 : 0,
      averageWin: winningTrades.length > 0 ? grossProfit / winningTrades.length : 0,
      averageLoss: losingTrades.length > 0 ? grossLoss / losingTrades.length : 0,
      largestWin: winningTrades.length > 0 ? Math.max(...winningTrades.map((t) => t.pnl)) : 0,
      largestLoss: losingTrades.length > 0 ? Math.min(...losingTrades.map((t) => t.pnl)) : 0,

      trades,
      equityCurve: this.equityCurve,
    };
  }
}
