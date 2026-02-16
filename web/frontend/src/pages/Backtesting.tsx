import { useState } from 'react';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import client from '../api/client';

export function Backtesting() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [strategyType, setStrategyType] = useState('grid');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const runBacktest = async () => {
    setRunning(true);
    setResult(null);
    try {
      const { data } = await client.post('/api/v1/backtesting/run', {
        strategy_type: strategyType,
        symbol,
        timeframe,
        start_date: '2024-01-01T00:00:00Z',
        end_date: '2024-12-31T23:59:59Z',
        initial_balance: '10000',
      });

      // Poll for result
      const jobId = data.job_id;
      let attempts = 0;
      while (attempts < 30) {
        await new Promise((r) => setTimeout(r, 2000));
        const { data: job } = await client.get(`/api/v1/backtesting/${jobId}`);
        if (job.status === 'completed') {
          setResult(job.result);
          break;
        }
        if (job.status === 'failed') {
          setResult({ error: job.error_message });
          break;
        }
        attempts++;
      }
    } catch {
      setResult({ error: 'Failed to run backtest' });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold text-text font-[Manrope] mb-6">Backtesting</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Parameters" className="lg:col-span-1">
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-text-muted mb-1">Strategy</label>
              <select
                value={strategyType}
                onChange={(e) => setStrategyType(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text"
              >
                <option value="grid">Grid</option>
                <option value="dca">DCA</option>
                <option value="trend_follower">Trend Follower</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Symbol</label>
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text"
              >
                {['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'ADAUSDT'].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Timeframe</label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text"
              >
                {['5m', '15m', '30m', '1h', '4h', '1d'].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <Button onClick={runBacktest} disabled={running} className="w-full">
              {running ? 'Running...' : 'Run Backtest'}
            </Button>
          </div>
        </Card>

        <Card title="Results" className="lg:col-span-2">
          {result ? (
            'error' in result ? (
              <p className="text-sm text-loss">{String(result.error)}</p>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-text-muted">Return</p>
                  <p className="text-lg font-bold text-profit">+{String(result.total_return_pct)}%</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Max Drawdown</p>
                  <p className="text-lg font-bold text-loss">{String(result.max_drawdown_pct)}%</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Sharpe Ratio</p>
                  <p className="text-lg font-bold text-text">{String(result.sharpe_ratio)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Win Rate</p>
                  <p className="text-lg font-bold text-text">{String(Number(result.win_rate) * 100)}%</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Total Trades</p>
                  <p className="text-lg font-bold text-text">{String(result.total_trades)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Profit Factor</p>
                  <p className="text-lg font-bold text-text">{String(result.profit_factor)}</p>
                </div>
              </div>
            )
          ) : (
            <p className="text-sm text-text-muted">Configure parameters and click "Run Backtest"</p>
          )}
        </Card>
      </div>
    </div>
  );
}
