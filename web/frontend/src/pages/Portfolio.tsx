import { useEffect, useState } from 'react';
import { Card } from '../components/common/Card';
import { Spinner } from '../components/common/Spinner';
import client from '../api/client';

interface PortfolioData {
  total_balance: string;
  total_realized_pnl: string;
  total_unrealized_pnl: string;
  active_bots: number;
  total_bots: number;
  allocation: Array<{ bot: string; strategy: string; symbol: string; profit: number }>;
}

export function Portfolio() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get('/api/v1/portfolio/summary')
      .then((res) => setData(res.data))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;

  const realized = parseFloat(data?.total_realized_pnl || '0');
  const unrealized = parseFloat(data?.total_unrealized_pnl || '0');

  return (
    <div>
      <h2 className="text-2xl font-bold text-text font-[Manrope] mb-6">Portfolio</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <p className="text-xs text-text-muted uppercase">Total Balance</p>
          <p className="text-2xl font-bold text-text mt-1">${parseFloat(data?.total_balance || '0').toFixed(2)}</p>
        </Card>
        <Card>
          <p className="text-xs text-text-muted uppercase">Realized PnL</p>
          <p className={`text-2xl font-bold mt-1 ${realized >= 0 ? 'text-profit' : 'text-loss'}`}>
            {realized >= 0 ? '+' : ''}{realized.toFixed(2)}$
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-muted uppercase">Unrealized PnL</p>
          <p className={`text-2xl font-bold mt-1 ${unrealized >= 0 ? 'text-profit' : 'text-loss'}`}>
            {unrealized >= 0 ? '+' : ''}{unrealized.toFixed(2)}$
          </p>
        </Card>
      </div>

      <Card title="Asset Allocation">
        {data?.allocation && data.allocation.length > 0 ? (
          <div className="space-y-2">
            {data.allocation.map((a) => (
              <div key={a.bot} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                <div>
                  <span className="text-sm font-medium text-text">{a.bot}</span>
                  <span className="text-xs text-text-muted ml-2">{a.symbol}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-muted">{a.strategy}</span>
                  <span className={`text-sm font-semibold ${a.profit >= 0 ? 'text-profit' : 'text-loss'}`}>
                    {a.profit >= 0 ? '+' : ''}{a.profit.toFixed(2)}$
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-muted">No allocation data</p>
        )}
      </Card>
    </div>
  );
}
