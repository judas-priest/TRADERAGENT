/**
 * Generate Reports Script
 * Automatically generates all report types from backtest results
 */

import { BacktestResults } from "../backtesting/BacktestRunner.js";
import { AdvancedMetrics } from "../backtesting/MetricsCalculator.js";
import { HTMLReportGenerator } from "../reports/HTMLReportGenerator.js";
import { CSVReportGenerator } from "../reports/CSVReportGenerator.js";
import {
  ComparisonReportGenerator,
  StrategyComparison,
} from "../reports/ComparisonReportGenerator.js";
import * as fs from "fs";
import * as path from "path";

interface BacktestFile {
  filename: string;
  filepath: string;
  results: BacktestResults;
  metrics: AdvancedMetrics;
}

function loadBacktestResults(directory: string): BacktestFile[] {
  console.log(`\n📂 Loading backtest results from: ${directory}`);

  if (!fs.existsSync(directory)) {
    console.error(`❌ Directory not found: ${directory}`);
    return [];
  }

  const files = fs
    .readdirSync(directory)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .reverse(); // Most recent first

  console.log(`   Found ${files.length} result files`);

  const backtests: BacktestFile[] = [];

  for (const filename of files) {
    const filepath = path.join(directory, filename);
    try {
      const data = JSON.parse(fs.readFileSync(filepath, "utf-8"));

      // Extract results and metrics
      const { advancedMetrics, generatedAt, ...results } = data;

      backtests.push({
        filename,
        filepath,
        results: results as BacktestResults,
        metrics: advancedMetrics as AdvancedMetrics,
      });

      console.log(`   ✓ Loaded: ${filename}`);
    } catch (error) {
      console.error(`   ✗ Error loading ${filename}:`, error.message);
    }
  }

  return backtests;
}

function generateIndividualReports(
  backtests: BacktestFile[],
  outputDir: string
): void {
  console.log(`\n📊 Generating individual reports...`);

  // Create output directories
  const htmlDir = path.join(outputDir, "html");
  const csvDir = path.join(outputDir, "csv");

  if (!fs.existsSync(htmlDir)) {
    fs.mkdirSync(htmlDir, { recursive: true });
  }
  if (!fs.existsSync(csvDir)) {
    fs.mkdirSync(csvDir, { recursive: true });
  }

  for (const backtest of backtests) {
    const baseName = backtest.filename.replace(".json", "");

    try {
      // Generate HTML report
      const htmlPath = path.join(htmlDir, `${baseName}.html`);
      HTMLReportGenerator.generate(
        backtest.results,
        backtest.metrics,
        htmlPath
      );

      // Generate CSV reports
      const csvBasePath = path.join(csvDir, baseName);
      if (!fs.existsSync(csvBasePath)) {
        fs.mkdirSync(csvBasePath, { recursive: true });
      }
      CSVReportGenerator.generateAll(
        backtest.results,
        backtest.metrics,
        csvBasePath
      );

      console.log(`   ✓ Generated reports for: ${backtest.results.strategy}`);
    } catch (error) {
      console.error(
        `   ✗ Error generating reports for ${baseName}:`,
        error.message
      );
    }
  }
}

function generateComparisonReports(
  backtests: BacktestFile[],
  outputDir: string
): void {
  console.log(`\n📊 Generating comparison reports...`);

  if (backtests.length < 2) {
    console.log("   ⚠️  Need at least 2 strategies to compare");
    return;
  }

  // Group by symbol and timeframe
  const groups = new Map<string, BacktestFile[]>();

  for (const backtest of backtests) {
    const key = `${backtest.results.symbol}_${backtest.results.timeframe}`;
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(backtest);
  }

  for (const [key, group] of groups) {
    if (group.length < 2) continue;

    const comparisons: StrategyComparison[] = group.map((b) => ({
      strategy: b.results.strategy,
      results: b.results,
      metrics: b.metrics,
    }));

    const [symbol, timeframe] = key.split("_");

    try {
      // Generate HTML comparison
      const htmlPath = path.join(
        outputDir,
        "html",
        `comparison_${symbol.replace("/", "-")}_${timeframe}.html`
      );
      ComparisonReportGenerator.generateHTML(comparisons, htmlPath);

      // Generate CSV comparison
      const csvPath = path.join(
        outputDir,
        "csv",
        `comparison_${symbol.replace("/", "-")}_${timeframe}.csv`
      );
      ComparisonReportGenerator.generateCSV(comparisons, csvPath);

      console.log(
        `   ✓ Generated comparison for: ${symbol} ${timeframe} (${group.length} strategies)`
      );
    } catch (error) {
      console.error(`   ✗ Error generating comparison for ${key}:`, error.message);
    }
  }
}

function generateSummaryIndex(
  backtests: BacktestFile[],
  outputDir: string
): void {
  console.log(`\n📄 Generating summary index...`);

  const htmlPath = path.join(outputDir, "index.html");

  const html = `<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Reports Index</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .section {
            padding: 40px;
        }
        .section h2 {
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        .report-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .report-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
            transition: transform 0.2s;
        }
        .report-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .report-card h3 {
            color: #667eea;
            margin-bottom: 10px;
        }
        .report-card .meta {
            color: #666;
            font-size: 0.9em;
            margin: 5px 0;
        }
        .report-card .links {
            margin-top: 15px;
        }
        .report-card a {
            display: inline-block;
            margin-right: 10px;
            margin-top: 5px;
            padding: 8px 15px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .report-card a:hover {
            background: #5568d3;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 10px;
        }
        .stat {
            background: #f3f4f6;
            padding: 10px;
            border-radius: 4px;
        }
        .stat .label {
            font-size: 0.8em;
            color: #666;
        }
        .stat .value {
            font-weight: bold;
            color: #333;
        }
        .stat .value.positive {
            color: #10b981;
        }
        .stat .value.negative {
            color: #ef4444;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Backtest Reports</h1>
            <div style="margin-top: 10px; opacity: 0.9;">Generated: ${new Date().toLocaleString()}</div>
        </div>

        <div class="section">
            <h2>📊 Available Reports (${backtests.length})</h2>
            <div class="report-grid">
                ${backtests
                  .map((b) => {
                    const baseName = b.filename.replace(".json", "");
                    const isProfit = b.results.totalReturn > 0;

                    return `
                    <div class="report-card">
                        <h3>${b.results.strategy}</h3>
                        <div class="meta">
                            ${b.results.symbol} • ${b.results.timeframe}
                        </div>
                        <div class="meta">
                            ${b.results.period.start} → ${b.results.period.end}
                        </div>
                        <div class="stats">
                            <div class="stat">
                                <div class="label">Return</div>
                                <div class="value ${isProfit ? "positive" : "negative"}">
                                    ${b.results.totalReturnPct >= 0 ? "+" : ""}${b.results.totalReturnPct.toFixed(2)}%
                                </div>
                            </div>
                            <div class="stat">
                                <div class="label">Sharpe</div>
                                <div class="value">${b.metrics.sharpeRatio.toFixed(2)}</div>
                            </div>
                            <div class="stat">
                                <div class="label">Trades</div>
                                <div class="value">${b.results.totalTrades}</div>
                            </div>
                            <div class="stat">
                                <div class="label">Win Rate</div>
                                <div class="value">${b.results.winRate.toFixed(1)}%</div>
                            </div>
                        </div>
                        <div class="links">
                            <a href="html/${baseName}.html">📄 View Report</a>
                            <a href="csv/${baseName}/summary.csv">📊 CSV</a>
                        </div>
                    </div>
                `;
                  })
                  .join("")}
            </div>
        </div>

        ${
          backtests.length >= 2
            ? `
        <div class="section">
            <h2>🔍 Comparison Reports</h2>
            <div class="report-grid">
                <div class="report-card">
                    <h3>Strategy Comparison</h3>
                    <div class="meta">Compare all strategies side-by-side</div>
                    <div class="links">
                        <a href="html/comparison_ETH-USDT_1h.html">📊 View Comparison</a>
                        <a href="csv/comparison_ETH-USDT_1h.csv">📄 CSV</a>
                    </div>
                </div>
            </div>
        </div>
        `
            : ""
        }

        <div style="padding: 20px; text-align: center; background: #f8f9fa; color: #666;">
            <p>TRADERAGENT Backtest Module • Powered by Claude Code</p>
        </div>
    </div>
</body>
</html>`;

  fs.writeFileSync(htmlPath, html);
  console.log(`   ✓ Summary index saved: ${htmlPath}`);
}

async function main() {
  console.log("\n🚀 TRADERAGENT Report Generator");
  console.log("=".repeat(70));

  const backtestsDir = "results/backtests";
  const reportsDir = "results/reports";

  // Load all backtest results
  const backtests = loadBacktestResults(backtestsDir);

  if (backtests.length === 0) {
    console.log("\n⚠️  No backtest results found!");
    console.log(`   Run backtests first: npm run backtest:full`);
    return;
  }

  // Generate individual reports
  generateIndividualReports(backtests, reportsDir);

  // Generate comparison reports
  generateComparisonReports(backtests, reportsDir);

  // Generate summary index
  generateSummaryIndex(backtests, reportsDir);

  console.log("\n✅ All reports generated successfully!");
  console.log("=".repeat(70));
  console.log(`\n📂 Reports location: ${reportsDir}/`);
  console.log(`   • Open ${reportsDir}/index.html to view all reports`);
  console.log(`   • HTML reports: ${reportsDir}/html/`);
  console.log(`   • CSV reports: ${reportsDir}/csv/\n`);
}

main().catch((error) => {
  console.error("❌ Error:", error.message);
  console.error(error.stack);
  process.exit(1);
});
