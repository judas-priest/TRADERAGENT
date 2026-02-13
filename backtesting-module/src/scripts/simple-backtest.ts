/**
 * Simple Backtest Script
 * Tests the data loading and basic backtest functionality
 */

import { CSVDataLoader } from "../adapters/CSVDataLoader.js";

async function main() {
  console.log("🚀 TRADERAGENT Backtest Module - Simple Test");
  console.log("=" .repeat(60));

  const loader = new CSVDataLoader();

  // List available data
  console.log("\n📊 Available Data Files:");
  const available = loader.listAvailableData();
  available.forEach((file) => {
    console.log(
      `   - ${file.exchange.toUpperCase()}: ${file.symbol} ${file.timeframe}`
    );
  });

  // Load sample data (Binance ETH/USDT 1h)
  console.log("\n📥 Loading Sample Data:");
  const candles = await loader.loadData("binance", "ETH/USDT", "1h");

  console.log(`\n📈 Data Statistics:`);
  console.log(`   Total candles: ${candles.length}`);
  console.log(`   First candle: ${candles[0].datetime}`);
  console.log(`   Last candle: ${candles[candles.length - 1].datetime}`);

  // Calculate simple metrics
  const prices = candles.map((c) => c.close);
  const maxPrice = Math.max(...prices);
  const minPrice = Math.min(...prices);
  const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length;

  console.log(`\n💰 Price Statistics:`);
  console.log(`   Max: $${maxPrice.toFixed(2)}`);
  console.log(`   Min: $${minPrice.toFixed(2)}`);
  console.log(`   Avg: $${avgPrice.toFixed(2)}`);
  console.log(`   Range: $${(maxPrice - minPrice).toFixed(2)}`);

  // Calculate total volume
  const totalVolume = candles.reduce((sum, c) => sum + c.volume, 0);
  console.log(`\n📊 Volume:`);
  console.log(`   Total: ${totalVolume.toFixed(2)} ETH`);
  console.log(`   Average: ${(totalVolume / candles.length).toFixed(2)} ETH/hour`);

  console.log("\n✅ Test completed successfully!");
  console.log("=" .repeat(60));
}

main().catch((error) => {
  console.error("❌ Error:", error.message);
  process.exit(1);
});
