import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { PageTransition } from '../components/common/PageTransition';
import { Skeleton } from '../components/common/Skeleton';
import { Toggle } from '../components/common/Toggle';
import { useToastStore } from '../components/common/Toast';
import { botsApi, type BotStatus, type BotUpdateRequest, type Position, type PnL } from '../api/bots';
import { WebSocketClient } from '../api/websocket';
import client from '../api/client';

// ─── Types ────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'settings' | 'logs';

interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  enum?: string[];
}

interface StrategyType {
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const statusVariant = (s: string) => {
  switch (s) {
    case 'running': return 'success' as const;
    case 'stopped': return 'default' as const;
    case 'paused': return 'warning' as const;
    case 'error': return 'error' as const;
    default: return 'default' as const;
  }
};

function formatUptime(seconds: number | null | undefined): string {
  if (!seconds) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

// ─── DynamicField (reused from CreateBotModal pattern) ────────────────────────

function DynamicField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const label = prop.title ?? name.replace(/_/g, ' ');
  const description = prop.description;

  if (prop.type === 'boolean') {
    return (
      <div className="flex items-center justify-between py-2">
        <div>
          <p className="text-sm text-text capitalize">{label}</p>
          {description && <p className="text-xs text-text-muted">{description}</p>}
        </div>
        <Toggle checked={Boolean(value)} onChange={onChange} />
      </div>
    );
  }

  if (prop.enum) {
    return (
      <div>
        <label className="block text-xs text-text-muted mb-1 capitalize">{label}</label>
        {description && <p className="text-xs text-text-muted mb-1">{description}</p>}
        <select
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
        >
          {prop.enum.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      </div>
    );
  }

  const isNumeric = prop.type === 'number' || prop.type === 'integer';
  const min = prop.minimum ?? prop.exclusiveMinimum;
  const max = prop.maximum ?? prop.exclusiveMaximum;

  return (
    <div>
      <label className="block text-xs text-text-muted mb-1 capitalize">{label}</label>
      {description && <p className="text-xs text-text-muted mb-1">{description}</p>}
      <input
        type={isNumeric ? 'number' : 'text'}
        value={String(value ?? '')}
        min={min}
        max={max}
        step={prop.type === 'integer' ? 1 : 'any'}
        onChange={(e) =>
          onChange(isNumeric ? (e.target.value === '' ? '' : Number(e.target.value)) : e.target.value)
        }
        className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
      />
    </div>
  );
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────

function OverviewTab({ bot, positions, pnl }: { bot: BotStatus; positions: Position[]; pnl: PnL | null }) {
  const profit = parseFloat(String(bot.total_profit ?? 0));

  return (
    <div className="space-y-6">
      {/* Status cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Status</p>
          <Badge variant={statusVariant(bot.status)}>{bot.status}</Badge>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Uptime</p>
          <p className="text-sm font-semibold text-text">{formatUptime(bot.uptime_seconds)}</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Total PnL</p>
          <p className={`text-sm font-semibold ${profit >= 0 ? 'text-profit' : 'text-loss'}`}>
            {profit >= 0 ? '+' : ''}{profit.toFixed(2)} USDT
          </p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Trades</p>
          <p className="text-sm font-semibold text-text">{bot.total_trades}</p>
        </div>
      </div>

      {/* PnL chart placeholder */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-4">PnL Chart</p>
        <div className="h-32 flex items-center justify-center rounded-lg bg-background border border-border/50">
          <p className="text-xs text-text-muted">Chart coming soon</p>
        </div>
      </div>

      {/* Active positions */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-4">Active Positions</p>
        {positions.length === 0 ? (
          <p className="text-sm text-text-muted">No active positions</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-border">
                  <th className="text-xs text-text-muted font-medium pb-2">Symbol</th>
                  <th className="text-xs text-text-muted font-medium pb-2">Side</th>
                  <th className="text-xs text-text-muted font-medium pb-2">Size</th>
                  <th className="text-xs text-text-muted font-medium pb-2">Entry Price</th>
                  <th className="text-xs text-text-muted font-medium pb-2">Unrealized PnL</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, i) => {
                  const upnl = pos.unrealized_pnl ? parseFloat(pos.unrealized_pnl) : null;
                  return (
                    <tr key={i} className="border-b border-border/50 last:border-0">
                      <td className="py-2 text-text">{pos.symbol}</td>
                      <td className="py-2">
                        <Badge variant={pos.side === 'buy' ? 'success' : 'error'}>{pos.side}</Badge>
                      </td>
                      <td className="py-2 text-text">{pos.size}</td>
                      <td className="py-2 text-text">{pos.entry_price}</td>
                      <td className={`py-2 font-medium ${upnl == null ? 'text-text-muted' : upnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                        {upnl == null ? '—' : `${upnl >= 0 ? '+' : ''}${upnl.toFixed(4)}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* PnL stats */}
      {pnl && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-4">Trade Statistics</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-text-muted">Win Rate</p>
              <p className="text-sm font-semibold text-text">
                {pnl.win_rate != null ? `${(pnl.win_rate * 100).toFixed(1)}%` : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Winning Trades</p>
              <p className="text-sm font-semibold text-profit">{pnl.winning_trades}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Losing Trades</p>
              <p className="text-sm font-semibold text-loss">{pnl.losing_trades}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Realized PnL</p>
              <p className={`text-sm font-semibold ${parseFloat(pnl.total_realized_pnl) >= 0 ? 'text-profit' : 'text-loss'}`}>
                {parseFloat(pnl.total_realized_pnl).toFixed(4)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Settings Tab ─────────────────────────────────────────────────────────────

function SettingsTab({ bot, onDeleted }: { bot: BotStatus; onDeleted: () => void }) {
  const toast = useToastStore((s) => s.add);
  const navigate = useNavigate();

  const [dryRun, setDryRun] = useState(bot.dry_run);
  const [strategyParams, setStrategyParams] = useState<Record<string, unknown>>(
    (bot.config as Record<string, unknown> | null) ?? {}
  );
  const [strategySchema, setStrategySchema] = useState<StrategyType | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Load strategy schema to build dynamic form
  useEffect(() => {
    setLoadingSchema(true);
    client
      .get<StrategyType[]>('/api/v1/strategies/types')
      .then((res) => {
        const found = res.data.find((s) => s.name === bot.strategy);
        if (found) setStrategySchema(found);
      })
      .catch(() => {/* ignore */})
      .finally(() => setLoadingSchema(false));
  }, [bot.strategy]);

  const handleSave = async () => {
    setSubmitting(true);
    try {
      const strategyKey = bot.strategy as 'grid' | 'dca' | 'trend_follower' | 'smc';
      const payload: BotUpdateRequest = {
        dry_run: dryRun,
        [strategyKey]: strategyParams,
      };
      await botsApi.update(bot.name, payload);
      toast('Settings saved', 'success');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail ?? 'Failed to save settings', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEmergencyStop = async () => {
    setStopping(true);
    try {
      await botsApi.emergencyStop(bot.name);
      toast(`Bot "${bot.name}" emergency stopped`, 'warning');
      navigate('/bots');
    } catch {
      toast('Emergency stop failed', 'error');
    } finally {
      setStopping(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await botsApi.delete(bot.name);
      toast(`Bot "${bot.name}" deleted`, 'success');
      onDeleted();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail ?? 'Failed to delete bot', 'error');
    } finally {
      setDeleting(false);
    }
  };

  const schemaProperties = strategySchema
    ? ((strategySchema.config_schema.properties ?? {}) as Record<string, SchemaProperty>)
    : {};
  const editableProperties = Object.entries(schemaProperties).filter(([key]) => key !== 'enabled');

  return (
    <div className="space-y-5">
      {/* Base settings */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-4">Base Configuration</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-text-muted mb-1">Bot Name</label>
            <input
              type="text"
              value={bot.name}
              disabled
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-muted cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Trading Pair</label>
            <input
              type="text"
              value={bot.symbol}
              disabled
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-muted cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Strategy</label>
            <input
              type="text"
              value={bot.strategy}
              disabled
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-muted cursor-not-allowed"
            />
          </div>
          <div className="flex items-center">
            <Toggle checked={dryRun} onChange={setDryRun} label="Dry Run (simulation)" disabled={submitting} />
          </div>
        </div>
      </div>

      {/* Strategy params */}
      {loadingSchema ? (
        <div className="bg-surface border border-border rounded-xl p-5">
          <Skeleton className="h-3 w-36 mb-4" />
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i}>
                <Skeleton className="h-3 w-20 mb-1" />
                <Skeleton className="h-9 w-full rounded-lg" />
              </div>
            ))}
          </div>
        </div>
      ) : editableProperties.length > 0 ? (
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-4">
            Strategy Parameters
          </p>
          <div className="space-y-3">
            {editableProperties.map(([key, prop]) => (
              <DynamicField
                key={key}
                name={key}
                prop={prop}
                value={strategyParams[key]}
                onChange={(v) => setStrategyParams((prev) => ({ ...prev, [key]: v }))}
              />
            ))}
          </div>
        </div>
      ) : null}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Button variant="danger" onClick={handleEmergencyStop} disabled={stopping || deleting || submitting}>
            {stopping ? 'Stopping…' : '⚠ Emergency Stop'}
          </Button>
          <Button variant="ghost" onClick={handleDelete} disabled={deleting || stopping || submitting}>
            {deleting ? 'Deleting…' : 'Delete Bot'}
          </Button>
        </div>
        <Button onClick={handleSave} disabled={submitting || stopping || deleting || loadingSchema}>
          {submitting ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}

// ─── Logs Tab ─────────────────────────────────────────────────────────────────

function LogsTab({ botName }: { botName: string }) {
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [connected, setConnected] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocketClient | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token') ?? '';
    const baseUrl = window.location.origin;
    const ws = new WebSocketClient(baseUrl);
    wsRef.current = ws;

    ws.connect(token, botName);

    // Poll connection state
    const pollInterval = setInterval(() => {
      setConnected(ws.isConnected);
    }, 1000);

    const unsubscribe = ws.onMessage((msg) => {
      const text =
        msg.type === 'log'
          ? String((msg.data as { message?: unknown })?.message ?? JSON.stringify(msg.data))
          : JSON.stringify(msg);
      setLogs((prev) => [...prev.slice(-999), text]);
    });

    return () => {
      clearInterval(pollInterval);
      unsubscribe();
      ws.disconnect();
    };
  }, [botName]);

  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-profit' : 'bg-loss'}`} />
          <span className="text-xs text-text-muted">{connected ? 'Connected' : 'Disconnected'}</span>
        </div>
        <div className="flex items-center gap-3">
          <Toggle checked={autoScroll} onChange={setAutoScroll} label="Auto-scroll" />
          <Button variant="ghost" size="sm" onClick={() => setLogs([])}>
            Clear
          </Button>
        </div>
      </div>

      <div className="bg-background border border-border rounded-xl p-4 h-96 overflow-y-auto font-mono text-xs text-text">
        {logs.length === 0 ? (
          <p className="text-text-muted">Waiting for logs…</p>
        ) : (
          logs.map((line, i) => (
            <div key={i} className="py-0.5 border-b border-border/30 last:border-0">
              {line}
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}

// ─── BotDetail Page ───────────────────────────────────────────────────────────

export function BotDetail() {
  const { botName } = useParams<{ botName: string }>();
  const navigate = useNavigate();
  const toast = useToastStore((s) => s.add);

  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [bot, setBot] = useState<BotStatus | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [pnl, setPnl] = useState<PnL | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = async () => {
    if (!botName) return;
    try {
      const [botRes, posRes, pnlRes] = await Promise.all([
        botsApi.get(botName),
        botsApi.getPositions(botName),
        botsApi.getPnl(botName),
      ]);
      setBot(botRes.data);
      setPositions(posRes.data);
      setPnl(pnlRes.data);
    } catch {
      toast('Failed to load bot data', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botName]);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'settings', label: 'Settings' },
    { id: 'logs', label: 'Logs' },
  ];

  if (isLoading) {
    return (
      <div>
        <div className="flex items-center gap-3 mb-6">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
        <div className="flex gap-2 mb-6">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-8 w-24 rounded-lg" />
          ))}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-surface border border-border rounded-xl p-4">
              <Skeleton className="h-3 w-16 mb-2" />
              <Skeleton className="h-5 w-20" />
            </div>
          ))}
        </div>
        <div className="bg-surface border border-border rounded-xl p-5">
          <Skeleton className="h-3 w-24 mb-4" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  if (!bot) {
    return (
      <div className="text-center py-12">
        <p className="text-text-muted mb-4">Bot not found</p>
        <Button onClick={() => navigate('/bots')}>← Back to Bots</Button>
      </div>
    );
  }

  return (
    <PageTransition>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <button
          onClick={() => navigate('/bots')}
          className="text-xs text-text-muted hover:text-text transition-colors"
        >
          ← Bots
        </button>
        <span className="text-border">/</span>
        <h2 className="text-2xl font-bold text-text font-[Manrope]">{bot.name}</h2>
        <Badge variant={statusVariant(bot.status)}>{bot.status}</Badge>
        <Badge variant="info">{bot.strategy}</Badge>
        <span className="text-xs text-text-muted">{bot.symbol}</span>
        {bot.dry_run && <Badge variant="warning">Dry Run</Badge>}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-surface border border-border rounded-lg p-1 w-fit">
        {tabs.map((tab) => (
          <motion.button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'bg-primary text-white'
                : 'text-text-muted hover:text-text'
            }`}
            whileTap={{ scale: 0.97 }}
          >
            {tab.label}
          </motion.button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <OverviewTab bot={bot} positions={positions} pnl={pnl} />
      )}
      {activeTab === 'settings' && (
        <SettingsTab bot={bot} onDeleted={() => navigate('/bots')} />
      )}
      {activeTab === 'logs' && (
        <LogsTab botName={bot.name} />
      )}
    </PageTransition>
  );
}
