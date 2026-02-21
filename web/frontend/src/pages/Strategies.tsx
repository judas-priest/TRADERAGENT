import { useEffect, useState } from 'react';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { PageTransition } from '../components/common/PageTransition';
import { SkeletonCard } from '../components/common/Skeleton';
import { useToastStore } from '../components/common/Toast';
import { CreateBotModal } from '../components/bots/CreateBotModal';
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
  config_json: string;
}

interface StrategyType {
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
  coming_soon: boolean;
}

export function Strategies() {
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [types, setTypes] = useState<StrategyType[]>([]);
  const [loading, setLoading] = useState(true);
  const toast = useToastStore((s) => s.add);

  // Create bot modal state (pre-filled from template copy)
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [presetStrategy, setPresetStrategy] = useState<string | undefined>();
  const [presetConfig, setPresetConfig] = useState<Record<string, unknown> | undefined>();

  useEffect(() => {
    Promise.all([
      client.get<StrategyTemplate[]>('/api/v1/strategies/templates'),
      client.get<StrategyType[]>('/api/v1/strategies/types'),
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
        deposit_amount: '100',
      });
      toast(`Strategy "${name}" copied successfully`, 'success');
    } catch {
      toast('Failed to copy strategy', 'error');
    }
  };

  /** Open Create Bot modal pre-filled from a template */
  const handleApplyToBot = (template: StrategyTemplate) => {
    let parsedConfig: Record<string, unknown> = {};
    try {
      const parsed = JSON.parse(template.config_json);
      // The config_json may contain the strategy-specific sub-key
      parsedConfig = (parsed[template.strategy_type] as Record<string, unknown>) ?? parsed;
    } catch {
      // ignore parse errors
    }
    setPresetStrategy(template.strategy_type);
    setPresetConfig(parsedConfig);
    setCreateModalOpen(true);
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
            <div
              key={t.name}
              className={`bg-background rounded-lg p-4 border transition-colors ${
                t.coming_soon
                  ? 'border-border opacity-50'
                  : 'border-border'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-sm font-semibold text-text capitalize">
                  {t.name.replace(/_/g, ' ')}
                </h4>
                {t.coming_soon && <Badge variant="default">Coming Soon</Badge>}
              </div>
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
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-text-muted">{t.copy_count} copies</span>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => handleCopy(t.id, t.name)}>
                    Copy
                  </Button>
                  <Button size="sm" onClick={() => handleApplyToBot(t)}>
                    Apply to Bot
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <CreateBotModal
        open={createModalOpen}
        onClose={() => {
          setCreateModalOpen(false);
          setPresetStrategy(undefined);
          setPresetConfig(undefined);
        }}
        onCreated={() => {}}
        strategyTypes={types}
        presetStrategy={presetStrategy}
        presetConfig={presetConfig}
      />
    </PageTransition>
  );
}
