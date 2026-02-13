/**
 * Full Backtest Script
 * Runs complete backtests with all metrics
 */

import { CSVDataLoader } from "../adapters/CSVDataLoader.js";
import { BacktestRunner, BacktestResults } from "../backtesting/BacktestRunner.js";
import { MetricsCalculator, AdvancedMetrics } from "../backtesting/MetricsCalculator.js";
import { SimpleSMCStrategy } from "../strategies/SimpleSMCStrategy.js";
import { SimpleTrendFollowerStrategy } from "../strategies/SimpleTrendFollowerStrategy.js";
import * as fs from "fs";
import * as path from "path";

function printResults(results: BacktestResults, metrics: AdvancedMetrics) {
  console.log("\n" + "=".repeat(70));
  console.log(`🚀 Backtest Results: ${results.strategy}`);
  console.log("=".repeat(70));
  console.log(
    `Period: ${results.period.start} to ${results.period.end}`
  );
  console.log(`Symbol: ${results.symbol}, Timeframe: ${results.timeframe}`);

  console.log(`\n💰 Performance:`);
  console.log(`   Initial Balance:    $${results.initialBalance.toFixed(2)}`);
  console.log(`   Final Balance:      $${results.finalBalance.toFixed(2)}`);
  console.log(
    `   Total Return:       ${results.totalReturn >= 0 ? "+" : ""}$${results.totalReturn.toFixed(2)} (${results.totalReturnPct >= 0 ? "+" : ""}${results.totalReturnPct.toFixed(2)}%)`
  );

  console.log(`\n📊 Trades:`);
  console.log(`   Total Trades:       ${results.totalTrades}`);
  console.log(
    `   Winning Trades:     ${results.winningTrades} (${results.winRate.toFixed(2)}%)`
  );
  console.log(`   Losing Trades:      ${results.losingTrades}`);

  console.log(`\n📈 Profit/Loss:`);
  console.log(`   Gross Profit:       $${results.grossProfit.toFixed(2)}`);
  console.log(`   Gross Loss:         $${results.grossLoss.toFixed(2)}`);
  console.log(`   Net Profit:         $${results.netProfit.toFixed(2)}`);
  console.log(`   Profit Factor:      ${results.profitFactor.toFixed(2)}`);
  console.log(`   Average Win:        $${results.averageWin.toFixed(2)}`);
  console.log(`   Average Loss:       $${results.averageLoss.toFixed(2)}`);
  console.log(`   Largest Win:        $${results.largestWin.toFixed(2)}`);
  console.log(`   Largest Loss:       $${results.largestLoss.toFixed(2)}`);

  console.log(`\n⚠️  Risk Metrics:`);
  console.log(`   Sharpe Ratio:       ${metrics.sharpeRatio.toFixed(2)}`);
  console.log(`   Sortino Ratio:      ${metrics.sortinoRatio.toFixed(2)}`);
  console.log(
    `   Max Drawdown:       $${metrics.maxDrawdown.toFixed(2)} (${metrics.maxDrawdownPct.toFixed(2)}%)`
  );
  console.log(`   Calmar Ratio:       ${metrics.calmarRatio.toFixed(2)}`);
  console.log(`   Recovery Factor:    ${metrics.recoveryFactor.toFixed(2)}`);
  console.log(`   Volatility:         ${(metrics.volatility * 100).toFixed(2)}%`);

  console.log(`\n⏱️  Trade Duration:`);
  console.log(`   Average:            ${metrics.averageTradeDuration.toFixed(1)} hours`);

  const overall =
    results.totalReturn > 0
      ? "✅ PROFITABLE"
      : results.totalReturn < 0
      ? "❌ LOSS"
      : "➖ BREAKEVEN";
  console.log(`\n${overall}`);
  console.log("=".repeat(70));
}

function saveResults(
  results: BacktestResults,
  metrics: AdvancedMetrics,
  outputDir: string
) {
  // Create output directory
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Save full results as JSON
  const fullData = {
    ...results,
    advancedMetrics: metrics,
    generatedAt: new Date().toISOString(),
  };

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, -5);
  const filename = `${timestamp}_${results.strategy.replace(/\s+/g, "-")}_${results.symbol.replace("/", "-")}_${results.timeframe}.json`;
  const filepath = path.join(outputDir, filename);

  fs.writeFileSync(filepath, JSON.stringify(fullData, null, 2));
  console.log(`\n💾 Results saved to: ${filepath}`);
}

async function main() {
  console.log("\n🚀 TRADERAGENT Full Backtest Runner");
  console.log("=".repeat(70));

  // Load data
  const loader = new CSVDataLoader();
  console.log("\n📥 Loading data...");
  const candles = await loader.loadData("binance", "ETH/USDT", "1h");

  // Initialize strategies
  const strategies = [
    new SimpleSMCStrategy(),
    new SimpleTrendFollowerStrategy(),
  ];

  // Run backtests
  const resultsDir = "results/backtests";

  for (const strategy of strategies) {
    const runner = new BacktestRunner({
      initialBalance: 10000,
      commission: 0.001, // 0.1%
      slippage: 0.0005, // 0.05%
      positionSize: 0.1, // 10% per trade
    });

    const results = await runner.run(
      strategy,
      candles,
      "ETH/USDT",
      "1h"
    );

    const metrics = MetricsCalculator.calculateAdvancedMetrics(results);

    printResults(results, metrics);
    saveResults(results, metrics, resultsDir);
  }

  console.log("\n✅ All backtests completed!");
  console.log("=".repeat(70));
}

main().catch((error) => {
  console.error("❌ Error:", error.message);
  console.error(error.stack);
  process.exit(1);
});
