import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { PageTransition } from '../components/common/PageTransition';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Skeleton } from '../components/common/Skeleton';
import { useToastStore } from '../components/common/Toast';
import { botsApi, type BotStatus, type PnL, type Position, type Trade } from '../api/bots';

type Tab = 'overview' | 'settings' | 'logs';

const statusVariant = (s: string) => {
  switch (s) {
    case 'running': return 'success' as const;
    case 'stopped': return 'default' as const;
    case 'paused': return 'warning' as const;
    case 'error': return 'error' as const;
    default: return 'default' as const;
  }
};

function formatUptime(seconds: number | null): string {
  if (!seconds) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function BotDetail() {
  const { botName } = useParams<{ botName: string }>();
  const navigate = useNavigate();
  const toast = useToastStore((s) => s.add);

  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [bot, setBot] = useState<BotStatus | null>(null);
  const [pnl, setPnl] = useState<PnL | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  // Settings edit state
  const [editConfig, setEditConfig] = useState<Record<string, unknown>>({});
  const [savingSettings, setSavingSettings] = useState(false);

  const fetchData = useCallback(async () => {
    if (!botName) return;
    try {
      const [botRes, pnlRes, posRes, tradeRes] = await Promise.all([
        botsApi.get(botName),
        botsApi.getPnl(botName),
        botsApi.getPositions(botName),
        botsApi.getTrades(botName, 50),
      ]);
      setBot(botRes.data);
      setPnl(pnlRes.data);
      setPositions(posRes.data);
      setTrades(tradeRes.data);
      setEditConfig(botRes.data.config ?? {});
    } catch {
      toast(`Failed to load bot "${botName}"`, 'error');
    } finally {
      setLoading(false);
    }
  }, [botName, toast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStart = async () => {
    if (!botName) return;
    setActionLoading(true);
    try {
      await botsApi.start(botName);
      toast(`Bot "${botName}" started`, 'success');
      fetchData();
    } catch {
      toast(`Failed to start "${botName}"`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    if (!botName) return;
    setActionLoading(true);
    try {
      await botsApi.stop(botName);
      toast(`Bot "${botName}" stopped`, 'info');
      fetchData();
    } catch {
      toast(`Failed to stop "${botName}"`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleEmergencyStop = async () => {
    if (!botName) return;
    if (!window.confirm(`Emergency stop "${botName}"? This will cancel all open orders.`)) return;
    setActionLoading(true);
    try {
      await botsApi.emergencyStop(botName);
      toast(`Bot "${botName}" emergency stopped`, 'warning');
      fetchData();
    } catch {
      toast(`Failed to emergency stop "${botName}"`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    if (!botName) return;
    setSavingSettings(true);
    try {
      await botsApi.update(botName, { trend_follower: editConfig });
      toast('Settings saved', 'success');
    } catch {
      toast('Failed to save settings', 'error');
    } finally {
      setSavingSettings(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-surface border border-border rounded-xl p-5">
              <Skeleton className="h-3 w-16 mb-2" />
              <Skeleton className="h-6 w-24" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!bot) {
    return (
      <div className="bg-surface border border-border rounded-xl p-12 text-center">
        <p className="text-text-muted">Bot not found</p>
        <Button variant="ghost" size="sm" onClick={() => navigate('/bots')} className="mt-4">
          ← Back to Bots
        </Button>
      </div>
    );
  }

  const profit = parseFloat(bot.total_profit);
  const winRate = pnl?.win_rate != null ? (pnl.win_rate * 100).toFixed(1) : null;

  return (
    <PageTransition>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <button
            onClick={() => navigate('/bots')}
            className="text-xs text-text-muted hover:text-text mb-1 flex items-center gap-1 transition-colors"
          >
            ← Bots
          </button>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-text font-[Manrope]">{bot.name}</h2>
            <Badge variant={statusVariant(bot.status)}>{bot.status}</Badge>
            {bot.dry_run && <Badge variant="warning">Dry Run</Badge>}
          </div>
          <p className="text-sm text-text-muted mt-0.5">
            {bot.strategy.replace('_', ' ')} · {bot.symbol}
          </p>
        </div>
        <div className="flex gap-2">
          {bot.status === 'running' ? (
            <Button variant="danger" size="sm" onClick={handleStop} disabled={actionLoading}>
              Stop
            </Button>
          ) : (
            <Button variant="primary" size="sm" onClick={handleStart} disabled={actionLoading}>
              Start
            </Button>
          )}
          <Button variant="danger" size="sm" onClick={handleEmergencyStop} disabled={actionLoading}>
            E-Stop
          </Button>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <p className="text-xs text-text-muted mb-1">Total PnL</p>
          <p className={`text-xl font-bold ${profit >= 0 ? 'text-profit' : 'text-loss'}`}>
            {profit >= 0 ? '+' : ''}{profit.toFixed(2)}$
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-muted mb-1">Total Trades</p>
          <p className="text-xl font-bold text-text">{bot.total_trades}</p>
        </Card>
        <Card>
          <p className="text-xs text-text-muted mb-1">Win Rate</p>
          <p className="text-xl font-bold text-text">{winRate != null ? `${winRate}%` : '—'}</p>
        </Card>
        <Card>
          <p className="text-xs text-text-muted mb-1">Uptime</p>
          <p className="text-xl font-bold text-text">{formatUptime(bot.uptime_seconds)}</p>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border mb-6">
        {(['overview', 'settings', 'logs'] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-text-muted hover:text-text'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          {/* Active positions */}
          <Card title="Active Positions">
            {positions.length === 0 ? (
              <p className="text-sm text-text-muted">No open positions</p>
            ) : (
              <div className="space-y-2">
                {positions.map((pos, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                    <div>
                      <span className="text-sm font-medium text-text">{pos.symbol}</span>
                      <span className={`ml-2 text-xs uppercase font-semibold ${pos.side === 'buy' ? 'text-profit' : 'text-loss'}`}>
                        {pos.side}
                      </span>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-text">{pos.size} @ ${pos.entry_price}</p>
                      {pos.unrealized_pnl != null && (
                        <p className={`text-xs ${parseFloat(pos.unrealized_pnl) >= 0 ? 'text-profit' : 'text-loss'}`}>
                          PnL: {parseFloat(pos.unrealized_pnl) >= 0 ? '+' : ''}{parseFloat(pos.unrealized_pnl).toFixed(2)}$
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Recent trades */}
          <Card title="Recent Trades">
            {trades.length === 0 ? (
              <p className="text-sm text-text-muted">No trades yet</p>
            ) : (
              <div className="space-y-0">
                <div className="grid grid-cols-4 text-xs text-text-muted pb-2 border-b border-border font-medium uppercase tracking-wide">
                  <span>Side</span>
                  <span>Price</span>
                  <span>Amount</span>
                  <span className="text-right">Profit</span>
                </div>
                {trades.map((trade) => (
                  <div key={trade.id} className="grid grid-cols-4 py-2 border-b border-border last:border-0 text-sm">
                    <span className={`font-medium ${trade.side === 'buy' ? 'text-profit' : 'text-loss'}`}>
                      {trade.side.toUpperCase()}
                    </span>
                    <span className="text-text">${parseFloat(trade.price).toFixed(2)}</span>
                    <span className="text-text">{parseFloat(trade.amount).toFixed(4)}</span>
                    <span className={`text-right ${trade.profit != null && parseFloat(trade.profit) >= 0 ? 'text-profit' : 'text-loss'}`}>
                      {trade.profit != null
                        ? `${parseFloat(trade.profit) >= 0 ? '+' : ''}${parseFloat(trade.profit).toFixed(2)}$`
                        : '—'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Settings tab */}
      {activeTab === 'settings' && (
        <Card title="Bot Configuration">
          <div className="space-y-3">
            <p className="text-xs text-text-muted">
              Editing bot configuration. Changes take effect after the bot is restarted.
            </p>
            {Object.keys(editConfig).length === 0 ? (
              <p className="text-sm text-text-muted">No configurable parameters available.</p>
            ) : (
              Object.entries(editConfig).map(([key, val]) => (
                <div key={key}>
                  <label className="block text-xs text-text-muted mb-1 capitalize">
                    {key.replace(/_/g, ' ')}
                  </label>
                  <input
                    type="text"
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-primary focus:outline-none"
                    value={String(val ?? '')}
                    onChange={(e) => setEditConfig((prev) => ({ ...prev, [key]: e.target.value }))}
                  />
                </div>
              ))
            )}
            <div className="pt-2">
              <Button variant="primary" size="sm" onClick={handleSaveSettings} disabled={savingSettings}>
                {savingSettings ? 'Saving…' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Logs tab */}
      {activeTab === 'logs' && (
        <Card title="Bot Logs">
          <div className="bg-background rounded-lg p-4 font-mono text-xs text-text-muted h-64 overflow-y-auto">
            <p className="text-text-muted italic">
              Live logs are streamed via WebSocket. Connect at{' '}
              <code className="text-primary">/ws/bots/{botName}/logs</code> for real-time output.
            </p>
            <p className="mt-2 text-text">
              [INFO] Bot <span className="text-profit">{botName}</span> status: {bot.status}
            </p>
            <p className="text-text">
              [INFO] Strategy: {bot.strategy} · Symbol: {bot.symbol}
            </p>
            <p className="text-text">[INFO] Total trades: {bot.total_trades}</p>
            {bot.open_orders > 0 && (
              <p className="text-text">[INFO] Open orders: {bot.open_orders}</p>
            )}
          </div>
        </Card>
      )}
    </PageTransition>
  );
}
