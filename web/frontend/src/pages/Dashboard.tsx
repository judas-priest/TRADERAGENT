import { useEffect, useState } from 'react';
import { Card } from '../components/common/Card';
import { Spinner } from '../components/common/Spinner';
import client from '../api/client';

interface DashboardData {
  active_bots: number;
  total_bots: number;
  total_profit: string;
  total_trades: number;
  bots: Array<{ name: string; strategy: string; symbol: string; status: string; total_profit: string }>;
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get('/api/v1/dashboard/overview')
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;

  const profit = parseFloat(data?.total_profit || '0');

  return (
    <div>
      <h2 className="text-2xl font-bold text-text font-[Manrope] mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <p className="text-xs text-text-muted uppercase">Active Bots</p>
          <p className="text-3xl font-bold text-blue mt-1">{data?.active_bots || 0}</p>
          <p className="text-xs text-text-muted mt-1">of {data?.total_bots || 0} total</p>
        </Card>
        <Card>
          <p className="text-xs text-text-muted uppercase">Total PnL</p>
          <p className={`text-3xl font-bold mt-1 ${profit >= 0 ? 'text-profit' : 'text-loss'}`}>
            {profit >= 0 ? '+' : ''}{profit.toFixed(2)}$
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-muted uppercase">Total Trades</p>
          <p className="text-3xl font-bold text-text mt-1">{data?.total_trades || 0}</p>
        </Card>
        <Card>
          <p className="text-xs text-text-muted uppercase">System Status</p>
          <div className="flex items-center gap-2 mt-2">
            <div className="w-3 h-3 rounded-full bg-profit animate-pulse" />
            <span className="text-lg font-semibold text-profit">Online</span>
          </div>
        </Card>
      </div>

      <Card title="Active Bots">
        {data?.bots && data.bots.length > 0 ? (
          <div className="space-y-2">
            {data.bots.map((bot) => {
              const botProfit = parseFloat(bot.total_profit);
              return (
                <div key={bot.name} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <div>
                    <span className="text-sm font-medium text-text">{bot.name}</span>
                    <span className="text-xs text-text-muted ml-2">{bot.symbol}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs px-2 py-0.5 bg-blue/20 text-blue rounded">{bot.strategy}</span>
                    <span className={`text-sm font-semibold ${botProfit >= 0 ? 'text-profit' : 'text-loss'}`}>
                      {botProfit >= 0 ? '+' : ''}{botProfit.toFixed(2)}$
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-text-muted">No active bots</p>
        )}
      </Card>
    </div>
  );
}
