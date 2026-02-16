import { useState } from 'react';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { PageTransition } from '../components/common/PageTransition';
import { Spinner } from '../components/common/Spinner';
import { useToastStore } from '../components/common/Toast';
import client from '../api/client';

export function Backtesting() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [strategyType, setStrategyType] = useState('grid');
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const toast = useToastStore((s) => s.add);

  const inputClass = 'w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary transition-colors';

  const runBacktest = async () => {
    setRunning(true);
    setResult(null);
    setProgress(0);
    try {
      const { data } = await client.post('/api/v1/backtesting/run', {
        strategy_type: strategyType,
        symbol,
        timeframe,
        start_date: '2024-01-01T00:00:00Z',
        end_date: '2024-12-31T23:59:59Z',
        initial_balance: '10000',
      });

      const jobId = data.job_id;
      let attempts = 0;
      while (attempts < 30) {
        await new Promise((r) => setTimeout(r, 2000));
        setProgress(Math.min(90, (attempts / 30) * 100));
        const { data: job } = await client.get(`/api/v1/backtesting/${jobId}`);
        if (job.status === 'completed') {
          setResult(job.result);
          setProgress(100);
          toast('Backtest completed', 'success');
          break;
        }
        if (job.status === 'failed') {
          setResult({ error: job.error_message });
          toast('Backtest failed', 'error');
          break;
        }
        attempts++;
      }
    } catch {
      setResult({ error: 'Failed to run backtest' });
      toast('Backtest error', 'error');
    } finally {
      setRunning(false);
    }
  };

  return (
    <PageTransition>
      <h2 className="text-2xl font-bold text-text font-[Manrope] mb-6">Backtesting</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Parameters" className="lg:col-span-1">
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-text-muted mb-1">Strategy</label>
              <select value={strategyType} onChange={(e) => setStrategyType(e.target.value)} className={inputClass}>
                <option value="grid">Grid</option>
                <option value="dca">DCA</option>
                <option value="trend_follower">Trend Follower</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Symbol</label>
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={inputClass}>
                {['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'ADAUSDT'].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Timeframe</label>
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={inputClass}>
                {['5m', '15m', '30m', '1h', '4h', '1d'].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            {running && (
              <div>
                <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                  <span>Progress</span>
                  <span>{Math.round(progress)}%</span>
                </div>
                <div className="w-full bg-border rounded-full h-1.5">
                  <div
                    className="bg-primary h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            <Button onClick={runBacktest} disabled={running} className="w-full">
              {running ? (
                <span className="flex items-center justify-center gap-2">
                  <Spinner size="sm" />
                  Running...
                </span>
              ) : 'Run Backtest'}
            </Button>
          </div>
        </Card>

        <Card title="Results" className="lg:col-span-2">
          {result ? (
            'error' in result ? (
              <p className="text-sm text-loss">{String(result.error)}</p>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                <ResultItem label="Return" value={`+${result.total_return_pct}%`} color="text-profit" />
                <ResultItem label="Max Drawdown" value={`${result.max_drawdown_pct}%`} color="text-loss" />
                <ResultItem label="Sharpe Ratio" value={String(result.sharpe_ratio)} />
                <ResultItem label="Win Rate" value={`${(Number(result.win_rate) * 100).toFixed(1)}%`} />
                <ResultItem label="Total Trades" value={String(result.total_trades)} />
                <ResultItem label="Profit Factor" value={String(result.profit_factor)} />
              </div>
            )
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-text-muted">
              <p className="text-sm">Configure parameters and click "Run Backtest"</p>
            </div>
          )}
        </Card>
      </div>
    </PageTransition>
  );
}

function ResultItem({ label, value, color = 'text-text' }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}
