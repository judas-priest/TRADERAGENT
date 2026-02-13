/**
 * Test Strategies Script
 * Tests signal generation from SMC and Trend-Follower strategies
 */

import { CSVDataLoader } from "../adapters/CSVDataLoader.js";
import { SimpleSMCStrategy } from "../strategies/SimpleSMCStrategy.js";
import { SimpleTrendFollowerStrategy } from "../strategies/SimpleTrendFollowerStrategy.js";
import { MarketContext } from "../strategies/IStrategy.js";

async function main() {
  console.log("🚀 TRADERAGENT Strategy Testing");
  console.log("=".repeat(60));

  // Load data
  const loader = new CSVDataLoader();
  console.log("\n📥 Loading ETH/USDT 1h data from Binance...");
  const candles = await loader.loadData("binance", "ETH/USDT", "1h");

  // Initialize strategies
  const smc = new SimpleSMCStrategy();
  const trendFollower = new SimpleTrendFollowerStrategy();

  console.log("\n📊 Testing Strategies:");
  console.log(`   - ${smc.name}`);
  console.log(`   - ${trendFollower.name}`);

  // Test on subset of data (1 month = ~720 hours)
  const testPeriod = Math.min(720, candles.length);
  console.log(`\n⏱️  Testing period: ${testPeriod} candles`);

  let smcSignals = 0;
  let trendFollowerSignals = 0;

  // Simulate through data
  for (let i = 0; i < testPeriod; i++) {
    const context: MarketContext = {
      candles,
      currentIndex: i,
      balance: 10000,
      openPosition: undefined,
    };

    const smcSignal = smc.analyze(candles[i], context);
    const tfSignal = trendFollower.analyze(candles[i], context);

    if (smcSignal) {
      smcSignals++;
      if (smcSignals <= 3) {
        // Show first 3 signals
        console.log(
          `\n📈 SMC Signal #${smcSignals}:`,
          `\n   Type: ${smcSignal.type}`,
          `\n   Price: $${smcSignal.price.toFixed(2)}`,
          `\n   SL: $${smcSignal.stopLoss?.toFixed(2)}`,
          `\n   TP: $${smcSignal.takeProfit?.toFixed(2)}`,
          `\n   Reason: ${smcSignal.reason}`
        );
      }
    }

    if (tfSignal) {
      trendFollowerSignals++;
      if (trendFollowerSignals <= 3) {
        // Show first 3 signals
        console.log(
          `\n📊 Trend-Follower Signal #${trendFollowerSignals}:`,
          `\n   Type: ${tfSignal.type}`,
          `\n   Price: $${tfSignal.price.toFixed(2)}`,
          `\n   SL: $${tfSignal.stopLoss?.toFixed(2)}`,
          `\n   TP: $${tfSignal.takeProfit?.toFixed(2)}`,
          `\n   Reason: ${tfSignal.reason}`
        );
      }
    }
  }

  console.log("\n" + "=".repeat(60));
  console.log("📊 Results:");
  console.log(`   SMC Signals: ${smcSignals}`);
  console.log(`   Trend-Follower Signals: ${trendFollowerSignals}`);
  console.log(`   Total Signals: ${smcSignals + trendFollowerSignals}`);
  console.log("\n✅ Strategy testing completed!");
  console.log("=".repeat(60));
}

main().catch((error) => {
  console.error("❌ Error:", error.message);
  process.exit(1);
});
