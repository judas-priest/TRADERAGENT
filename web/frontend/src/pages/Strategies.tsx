import { useEffect, useState } from 'react';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { PageTransition } from '../components/common/PageTransition';
import { SkeletonCard } from '../components/common/Skeleton';
import { useToastStore } from '../components/common/Toast';
import client from '../api/client';

interface StrategyTemplate {
  id: number;
  name: string;
  description: string;
  strategy_type: string;
  risk_level: string;
  min_deposit: string;
  expected_pnl_pct: string | null;
  copy_count: number;
}

interface StrategyType {
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
}

export function Strategies() {
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [types, setTypes] = useState<StrategyType[]>([]);
  const [loading, setLoading] = useState(true);
  const toast = useToastStore((s) => s.add);

  useEffect(() => {
    Promise.all([
      client.get('/api/v1/strategies/templates'),
      client.get('/api/v1/strategies/types'),
    ]).then(([tRes, tyRes]) => {
      setTemplates(tRes.data);
      setTypes(tyRes.data);
    }).finally(() => setLoading(false));
  }, []);

  const riskVariant = (r: string) => {
    switch (r) {
      case 'low': return 'success' as const;
      case 'medium': return 'warning' as const;
      case 'high': return 'error' as const;
      default: return 'default' as const;
    }
  };

  const handleCopy = async (templateId: number, name: string) => {
    try {
      await client.post('/api/v1/strategies/copy', {
        template_id: templateId,
        bot_name: `${name}-copy`,
        symbol: 'BTCUSDT',
      });
      toast(`Strategy "${name}" copied successfully`, 'success');
    } catch {
      toast('Failed to copy strategy', 'error');
    }
  };

  if (loading) {
    return (
      <div>
        <div className="h-7 w-48 animate-pulse bg-border/50 rounded mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  return (
    <PageTransition>
      <h2 className="text-2xl font-bold text-text font-[Manrope] mb-6">Strategy Marketplace</h2>

      <Card title="Available Strategy Types" className="mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {types.map((t) => (
            <div key={t.name} className="bg-background rounded-lg p-4 border border-border">
              <h4 className="text-sm font-semibold text-text mb-1 capitalize">{t.name.replace('_', ' ')}</h4>
              <p className="text-xs text-text-muted">{t.description}</p>
            </div>
          ))}
        </div>
      </Card>

      <h3 className="text-lg font-semibold text-text mb-4">Templates</h3>
      {templates.length === 0 ? (
        <Card>
          <p className="text-sm text-text-muted">No strategy templates available yet. Admins can create them.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((t) => (
            <Card key={t.id}>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-text">{t.name}</h4>
                <Badge variant={riskVariant(t.risk_level)}>{t.risk_level} risk</Badge>
              </div>
              <p className="text-xs text-text-muted mb-3">{t.description}</p>
              <div className="grid grid-cols-2 gap-2 mb-3">
                <div>
                  <p className="text-xs text-text-muted">Min Deposit</p>
                  <p className="text-sm font-semibold text-text">${t.min_deposit}</p>
                </div>
                {t.expected_pnl_pct && (
                  <div>
                    <p className="text-xs text-text-muted">Expected PnL</p>
                    <p className="text-sm font-semibold text-profit">+{t.expected_pnl_pct}%</p>
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">{t.copy_count} copies</span>
                <Button size="sm" onClick={() => handleCopy(t.id, t.name)}>Copy Strategy</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </PageTransition>
  );
}
