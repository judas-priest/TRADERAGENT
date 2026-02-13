/**
 * Test Report Generator
 *
 * Generates comprehensive HTML reports with:
 * - Interactive charts (PnL, reversals, lot history)
 * - Detailed test results
 * - State transition diagrams
 * - Markdown summary for PRs
 */

export interface TestResult {
  scenario: {
    name: string;
    description: string;
    expectedOutcome: {
      finalState: string;
      pnl: number;
      reversals: number;
    };
  };
  metrics: {
    finalState: string;
    totalPnL: number;
    reversalCount: number;
    totalTrades: number;
    successfulTrades: number;
    failedTrades: number;
    stateTransitions: Array<{ from: string; to: string; event: string; timestamp: number }>;
    lotHistory: number[];
  };
  passed: boolean;
  duration: number;
  errors?: string[];
}

export class TestReportGenerator {
  /**
   * Generate HTML report with interactive charts
   */
  generateHTML(results: TestResult[]): string {
    const passedCount = results.filter(r => r.passed).length;
    const totalCount = results.length;
    const passRate = (passedCount / totalCount * 100).toFixed(1);

    return `
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Martingale Strategy Test Results</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      color: #333;
      background: #f5f5f5;
      padding: 20px;
    }

    .container {
      max-width: 1400px;
      margin: 0 auto;
      background: white;
      padding: 40px;
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    h1 {
      font-size: 32px;
      margin-bottom: 10px;
      color: #2c3e50;
    }

    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
      margin: 30px 0;
    }

    .summary-card {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 24px;
      border-radius: 8px;
      text-align: center;
    }

    .summary-card.success {
      background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    }

    .summary-card.danger {
      background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
    }

    .summary-card h3 {
      font-size: 14px;
      opacity: 0.9;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 1px;
    }

    .summary-card .value {
      font-size: 36px;
      font-weight: bold;
    }

    .scenario {
      border: 1px solid #e0e0e0;
      margin: 30px 0;
      padding: 24px;
      border-radius: 8px;
      transition: box-shadow 0.3s;
    }

    .scenario:hover {
      box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    .scenario.pass {
      border-left: 4px solid #11998e;
      background: #f0fff4;
    }

    .scenario.fail {
      border-left: 4px solid #eb3349;
      background: #fff5f5;
    }

    .scenario h2 {
      font-size: 20px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
    }

    .badge.pass {
      background: #11998e;
      color: white;
    }

    .badge.fail {
      background: #eb3349;
      color: white;
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin: 20px 0;
    }

    .metric {
      background: #f8f9fa;
      padding: 16px;
      border-radius: 6px;
    }

    .metric .label {
      font-size: 12px;
      color: #6c757d;
      margin-bottom: 4px;
    }

    .metric .value {
      font-size: 24px;
      font-weight: 600;
      color: #2c3e50;
    }

    .metric .expected {
      font-size: 12px;
      color: #6c757d;
      margin-top: 4px;
    }

    .lot-history {
      margin: 20px 0;
      padding: 16px;
      background: #f8f9fa;
      border-radius: 6px;
    }

    .lot-history h3 {
      font-size: 14px;
      color: #6c757d;
      margin-bottom: 8px;
    }

    .lot-history .lots {
      font-family: 'Courier New', monospace;
      font-size: 14px;
      color: #2c3e50;
    }

    .chart {
      margin: 30px 0;
      height: 400px;
    }

    .state-transitions {
      margin: 20px 0;
      background: #f8f9fa;
      padding: 16px;
      border-radius: 6px;
      max-height: 300px;
      overflow-y: auto;
    }

    .state-transitions h3 {
      font-size: 14px;
      color: #6c757d;
      margin-bottom: 8px;
    }

    .transition {
      font-family: 'Courier New', monospace;
      font-size: 12px;
      padding: 4px 0;
      color: #495057;
    }

    .error-list {
      margin: 20px 0;
      padding: 16px;
      background: #fff5f5;
      border-left: 4px solid #eb3349;
      border-radius: 4px;
    }

    .error-list h3 {
      color: #eb3349;
      margin-bottom: 8px;
    }

    .error-list li {
      margin-left: 20px;
      color: #c53030;
    }

    footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #e0e0e0;
      text-align: center;
      color: #6c757d;
      font-size: 14px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>📊 Martingale Strategy Test Results</h1>
    <p style="color: #6c757d; margin-top: 10px;">Комплексное тестирование стратегии Price Channel Martingale</p>

    <div class="summary">
      <div class="summary-card ${passRate === '100.0' ? 'success' : (parseFloat(passRate) >= 70 ? '' : 'danger')}">
        <h3>Pass Rate</h3>
        <div class="value">${passRate}%</div>
      </div>
      <div class="summary-card">
        <h3>Total Tests</h3>
        <div class="value">${totalCount}</div>
      </div>
      <div class="summary-card success">
        <h3>Passed</h3>
        <div class="value">${passedCount}</div>
      </div>
      <div class="summary-card ${totalCount - passedCount > 0 ? 'danger' : ''}">
        <h3>Failed</h3>
        <div class="value">${totalCount - passedCount}</div>
      </div>
    </div>

    <div id="pnl-chart" class="chart"></div>
    <div id="reversals-chart" class="chart"></div>

    ${results.map(r => this.renderScenario(r)).join('\n')}

    <footer>
      <p>Generated on ${new Date().toLocaleString('ru-RU')}</p>
      <p>🤖 Generated with Claude Code</p>
    </footer>
  </div>

  <script>
    ${this.generateChartJS(results)}
  </script>
</body>
</html>
    `;
  }

  /**
   * Render a single scenario result
   */
  private renderScenario(result: TestResult): string {
    const status = result.passed ? 'pass' : 'fail';
    const badge = result.passed ? 'PASSED' : 'FAILED';

    return `
      <div class="scenario ${status}">
        <h2>
          ${result.scenario.name}
          <span class="badge ${status}">✓ ${badge}</span>
        </h2>
        <p style="color: #6c757d; margin-bottom: 16px;">${result.scenario.description}</p>

        <div class="metrics">
          <div class="metric">
            <div class="label">Final State</div>
            <div class="value" style="font-size: 16px;">${result.metrics.finalState}</div>
            <div class="expected">expected: ${result.scenario.expectedOutcome.finalState}</div>
          </div>

          <div class="metric">
            <div class="label">PnL</div>
            <div class="value" style="color: ${result.metrics.totalPnL >= 0 ? '#11998e' : '#eb3349'};">
              ${result.metrics.totalPnL >= 0 ? '+' : ''}$${result.metrics.totalPnL.toFixed(2)}
            </div>
            <div class="expected">expected: $${result.scenario.expectedOutcome.pnl}</div>
          </div>

          <div class="metric">
            <div class="label">Reversals</div>
            <div class="value">${result.metrics.reversalCount}</div>
            <div class="expected">expected: ${result.scenario.expectedOutcome.reversals}</div>
          </div>

          <div class="metric">
            <div class="label">Trades</div>
            <div class="value">${result.metrics.totalTrades}</div>
            <div class="expected">
              ✅ ${result.metrics.successfulTrades} / ❌ ${result.metrics.failedTrades}
            </div>
          </div>

          <div class="metric">
            <div class="label">Duration</div>
            <div class="value" style="font-size: 18px;">${result.duration.toFixed(2)}s</div>
          </div>
        </div>

        ${result.metrics.lotHistory.length > 0 ? `
          <div class="lot-history">
            <h3>История лотов:</h3>
            <div class="lots">${result.metrics.lotHistory.map((l, i) => {
              const arrow = i < result.metrics.lotHistory.length - 1 ? ' → ' : '';
              return l.toFixed(3) + arrow;
            }).join('')}</div>
          </div>
        ` : ''}

        <div class="state-transitions">
          <h3>State Transitions (${result.metrics.stateTransitions.length}):</h3>
          ${result.metrics.stateTransitions.slice(0, 10).map(t =>
            `<div class="transition">${t.from} → ${t.to}</div>`
          ).join('\n')}
          ${result.metrics.stateTransitions.length > 10 ? `<div class="transition">... и еще ${result.metrics.stateTransitions.length - 10} переходов</div>` : ''}
        </div>

        ${result.errors && result.errors.length > 0 ? `
          <div class="error-list">
            <h3>Ошибки:</h3>
            <ul>
              ${result.errors.map(e => `<li>${e}</li>`).join('\n')}
            </ul>
          </div>
        ` : ''}
      </div>
    `;
  }

  /**
   * Generate Plotly.js chart code
   */
  private generateChartJS(results: TestResult[]): string {
    return `
      // PnL Chart
      Plotly.newPlot('pnl-chart', [{
        x: ${JSON.stringify(results.map(r => r.scenario.name))},
        y: ${JSON.stringify(results.map(r => r.metrics.totalPnL))},
        type: 'bar',
        marker: {
          color: ${JSON.stringify(results.map(r => r.metrics.totalPnL >= 0 ? '#11998e' : '#eb3349'))}
        },
        text: ${JSON.stringify(results.map(r => '$' + r.metrics.totalPnL.toFixed(2)))},
        textposition: 'outside',
      }], {
        title: 'PnL по сценариям',
        xaxis: { title: 'Сценарий' },
        yaxis: { title: 'USD' },
        height: 400,
      });

      // Reversals Chart
      Plotly.newPlot('reversals-chart', [{
        x: ${JSON.stringify(results.map(r => r.scenario.name))},
        y: ${JSON.stringify(results.map(r => r.metrics.reversalCount))},
        type: 'bar',
        marker: {
          color: '#667eea'
        },
        text: ${JSON.stringify(results.map(r => r.metrics.reversalCount.toString()))},
        textposition: 'outside',
      }], {
        title: 'Количество разворотов',
        xaxis: { title: 'Сценарий' },
        yaxis: { title: 'Count' },
        height: 400,
      });
    `;
  }

  /**
   * Generate Markdown summary for Pull Requests
   */
  generateMarkdown(results: TestResult[]): string {
    const passedCount = results.filter(r => r.passed).length;
    const totalCount = results.length;
    const passRate = (passedCount / totalCount * 100).toFixed(1);

    let markdown = `## 📊 Martingale Integration Test Results\n\n`;
    markdown += `**Summary:** ${passedCount}/${totalCount} tests passed (${passRate}%)\n\n`;

    // Table header
    markdown += `| Scenario | Status | PnL | Reversals | Trades | Duration |\n`;
    markdown += `|----------|--------|-----|-----------|--------|----------|\n`;

    // Table rows
    for (const result of results) {
      const status = result.passed ? '✅ PASS' : '❌ FAIL';
      const pnlFormatted = `$${result.metrics.totalPnL.toFixed(2)}`;
      const row = [
        result.scenario.name,
        status,
        pnlFormatted,
        result.metrics.reversalCount.toString(),
        result.metrics.totalTrades.toString(),
        `${result.duration.toFixed(2)}s`,
      ];
      markdown += `| ${row.join(' | ')} |\n`;
    }

    markdown += `\n---\n`;
    markdown += `\n_Generated on ${new Date().toLocaleString('ru-RU')}_\n`;

    return markdown;
  }

  /**
   * Generate JSON summary
   */
  generateJSON(results: TestResult[]): string {
    const passedCount = results.filter(r => r.passed).length;
    const totalCount = results.length;

    return JSON.stringify({
      summary: {
        total: totalCount,
        passed: passedCount,
        failed: totalCount - passedCount,
        passRate: (passedCount / totalCount * 100).toFixed(1) + '%',
      },
      results: results.map(r => ({
        scenario: r.scenario.name,
        passed: r.passed,
        metrics: {
          finalState: r.metrics.finalState,
          pnl: r.metrics.totalPnL,
          reversals: r.metrics.reversalCount,
          trades: r.metrics.totalTrades,
        },
        duration: r.duration,
      })),
      timestamp: new Date().toISOString(),
    }, null, 2);
  }
}
