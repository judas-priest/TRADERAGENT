/**
 * CSV Data Loader
 * Loads historical OHLCV data from CSV files
 */

import * as fs from "fs";
import * as path from "path";

export interface Candle {
  timestamp: number;
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export class CSVDataLoader {
  private dataDir: string;

  constructor(dataDir: string = "data/historical") {
    this.dataDir = dataDir;
  }

  /**
   * Load OHLCV data from CSV file
   */
  async loadData(
    exchange: "binance" | "bybit",
    symbol: string,
    timeframe: string
  ): Promise<Candle[]> {
    const filename = `${exchange}_${symbol.replace("/", "_")}_${timeframe}.csv`;
    const filepath = path.join(this.dataDir, filename);

    if (!fs.existsSync(filepath)) {
      throw new Error(`Data file not found: ${filepath}`);
    }

    const content = fs.readFileSync(filepath, "utf-8");
    const lines = content.trim().split("\n");

    // Skip header
    const dataLines = lines.slice(1);

    const candles: Candle[] = dataLines.map((line) => {
      const [timestamp, datetime, open, high, low, close, volume] =
        line.split(",");

      return {
        timestamp: parseInt(timestamp),
        datetime: datetime,
        open: parseFloat(open),
        high: parseFloat(high),
        low: parseFloat(low),
        close: parseFloat(close),
        volume: parseFloat(volume),
      };
    });

    console.log(
      `✅ Loaded ${candles.length} candles from ${filename}`
    );
    console.log(
      `   Period: ${candles[0].datetime} to ${candles[candles.length - 1].datetime}`
    );

    return candles;
  }

  /**
   * Get available data files
   */
  listAvailableData(): Array<{
    exchange: string;
    symbol: string;
    timeframe: string;
    filename: string;
  }> {
    const files = fs.readdirSync(this.dataDir);
    const csvFiles = files.filter((f) => f.endsWith(".csv"));

    return csvFiles.map((filename) => {
      // Parse filename: exchange_SYMBOL_timeframe.csv
      const parts = filename.replace(".csv", "").split("_");
      return {
        exchange: parts[0],
        symbol: parts.slice(1, -1).join("_").replace("_", "/"),
        timeframe: parts[parts.length - 1],
        filename,
      };
    });
  }
}
