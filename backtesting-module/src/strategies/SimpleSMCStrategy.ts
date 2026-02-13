/**
 * Simplified SMC Strategy for Backtesting
 * Based on TRADERAGENT SMC Strategy but simplified for single-timeframe testing
 */

import {
  IStrategy,
  Signal,
  MarketContext,
  calculateEMA,
  calculateATR,
  calculateRSI,
} from "./IStrategy.js";
import { Candle } from "../adapters/CSVDataLoader.js";

export interface SMCConfig {
  // EMA periods for trend
  emaFast: number;
  emaSlow: number;

  // ATR for stop-loss
  atrPeriod: number;
  atrMultiplier: number;

  // RSI for overbought/oversold
  rsiPeriod: number;
  rsiOverbought: number;
  rsiOversold: number;

  // Risk/Reward
  riskRewardRatio: number;
}

const DEFAULT_CONFIG: SMCConfig = {
  emaFast: 12,
  emaSlow: 26,
  atrPeriod: 14,
  atrMultiplier: 2.0,
  rsiPeriod: 14,
  rsiOverbought: 70,
  rsiOversold: 30,
  riskRewardRatio: 2.0,
};

/**
 * Simplified SMC Strategy
 *
 * Logic:
 * - Trend: EMA crossover (fast > slow = uptrend)
 * - Entry: RSI confirmation + trend alignment
 * - Stop-Loss: ATR-based
 * - Take-Profit: Risk/Reward ratio
 */
export class SimpleSMCStrategy implements IStrategy {
  public readonly name = "Simplified SMC";
  public readonly description =
    "EMA trend + RSI confirmation with ATR-based stops";

  private config: SMCConfig;
  private emaFastValue: number | null = null;
  private emaSlowValue: number | null = null;

  constructor(config: Partial<SMCConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  analyze(candle: Candle, context: MarketContext): Signal | null {
    const { candles, currentIndex, openPosition } = context;

    // Need enough data for indicators
    if (currentIndex < Math.max(this.config.emaSlow, this.config.atrPeriod)) {
      return null;
    }

    // Don't open new position if one is already open
    if (openPosition) {
      return null;
    }

    // Get historical prices
    const closes = candles.slice(0, currentIndex + 1).map((c) => c.close);

    // Calculate EMA
    this.emaFastValue = calculateEMA(closes, this.config.emaFast, this.emaFastValue);
    this.emaSlowValue = calculateEMA(closes, this.config.emaSlow, this.emaSlowValue);

    if (!this.emaFastValue || !this.emaSlowValue) {
      return null;
    }

    // Calculate RSI
    const rsi = calculateRSI(closes, this.config.rsiPeriod);
    if (!rsi) {
      return null;
    }

    // Calculate ATR for stop-loss
    const recentCandles = candles.slice(
      Math.max(0, currentIndex - this.config.atrPeriod),
      currentIndex + 1
    );
    const atr = calculateATR(recentCandles, this.config.atrPeriod);
    if (!atr) {
      return null;
    }

    // Determine trend
    const isUptrend = this.emaFastValue > this.emaSlowValue;
    const isDowntrend = this.emaFastValue < this.emaSlowValue;

    // BUY Signal: Uptrend + RSI oversold (recovery)
    if (isUptrend && rsi < this.config.rsiOversold) {
      const stopLoss = candle.close - atr * this.config.atrMultiplier;
      const takeProfit =
        candle.close +
        atr * this.config.atrMultiplier * this.config.riskRewardRatio;

      return {
        type: "BUY",
        timestamp: candle.timestamp,
        price: candle.close,
        stopLoss,
        takeProfit,
        reason: `Uptrend + RSI oversold (${rsi.toFixed(1)})`,
        confidence: 0.7,
      };
    }

    // SELL Signal: Downtrend + RSI overbought (reversal)
    if (isDowntrend && rsi > this.config.rsiOverbought) {
      const stopLoss = candle.close + atr * this.config.atrMultiplier;
      const takeProfit =
        candle.close -
        atr * this.config.atrMultiplier * this.config.riskRewardRatio;

      return {
        type: "SELL",
        timestamp: candle.timestamp,
        price: candle.close,
        stopLoss,
        takeProfit,
        reason: `Downtrend + RSI overbought (${rsi.toFixed(1)})`,
        confidence: 0.7,
      };
    }

    return null;
  }

  reset(): void {
    this.emaFastValue = null;
    this.emaSlowValue = null;
  }

  getStats() {
    return {
      emaFast: this.emaFastValue,
      emaSlow: this.emaSlowValue,
    };
  }
}
