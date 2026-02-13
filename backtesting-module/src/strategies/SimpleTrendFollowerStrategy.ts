/**
 * Simplified Trend-Follower Strategy
 * Follows trends with EMA and momentum confirmation
 */

import {
  IStrategy,
  Signal,
  MarketContext,
  calculateEMA,
  calculateATR,
} from "./IStrategy.js";
import { Candle } from "../adapters/CSVDataLoader.js";

export interface TrendFollowerConfig {
  emaShort: number;
  emaMedium: number;
  emaLong: number;
  atrPeriod: number;
  atrMultiplier: number;
  riskRewardRatio: number;
}

const DEFAULT_CONFIG: TrendFollowerConfig = {
  emaShort: 8,
  emaMedium: 21,
  emaLong: 55,
  atrPeriod: 14,
  atrMultiplier: 1.5,
  riskRewardRatio: 2.5,
};

export class SimpleTrendFollowerStrategy implements IStrategy {
  public readonly name = "Simplified Trend-Follower";
  public readonly description = "Triple EMA trend following with ATR stops";

  private config: TrendFollowerConfig;
  private emaShortValue: number | null = null;
  private emaMediumValue: number | null = null;
  private emaLongValue: number | null = null;

  constructor(config: Partial<TrendFollowerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  analyze(candle: Candle, context: MarketContext): Signal | null {
    const { candles, currentIndex, openPosition } = context;

    if (currentIndex < this.config.emaLong) {
      return null;
    }

    if (openPosition) {
      return null;
    }

    const closes = candles.slice(0, currentIndex + 1).map((c) => c.close);

    // Calculate EMAs
    this.emaShortValue = calculateEMA(closes, this.config.emaShort, this.emaShortValue);
    this.emaMediumValue = calculateEMA(closes, this.config.emaMedium, this.emaMediumValue);
    this.emaLongValue = calculateEMA(closes, this.config.emaLong, this.emaLongValue);

    if (!this.emaShortValue || !this.emaMediumValue || !this.emaLongValue) {
      return null;
    }

    const recentCandles = candles.slice(
      Math.max(0, currentIndex - this.config.atrPeriod),
      currentIndex + 1
    );
    const atr = calculateATR(recentCandles, this.config.atrPeriod);
    if (!atr) {
      return null;
    }

    // Strong uptrend: short > medium > long
    const isStrongUptrend =
      this.emaShortValue > this.emaMediumValue &&
      this.emaMediumValue > this.emaLongValue;

    // Strong downtrend: short < medium < long
    const isStrongDowntrend =
      this.emaShortValue < this.emaMediumValue &&
      this.emaMediumValue < this.emaLongValue;

    if (isStrongUptrend) {
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
        reason: "Strong uptrend (EMA alignment)",
        confidence: 0.8,
      };
    }

    if (isStrongDowntrend) {
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
        reason: "Strong downtrend (EMA alignment)",
        confidence: 0.8,
      };
    }

    return null;
  }

  reset(): void {
    this.emaShortValue = null;
    this.emaMediumValue = null;
    this.emaLongValue = null;
  }

  getStats() {
    return {
      emaShort: this.emaShortValue,
      emaMedium: this.emaMediumValue,
      emaLong: this.emaLongValue,
    };
  }
}
