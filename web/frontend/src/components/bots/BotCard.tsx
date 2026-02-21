import { motion } from 'framer-motion';
import type { BotListItem } from '../../api/bots';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';

interface BotCardProps {
  bot: BotListItem;
  onStart?: () => void;
  onStop?: () => void;
  onClick?: () => void;
}

const statusVariant = (s: string) => {
  switch (s) {
    case 'running': return 'success' as const;
    case 'stopped': return 'default' as const;
    case 'paused': return 'warning' as const;
    case 'error': return 'error' as const;
    default: return 'default' as const;
  }
};

const STRATEGY_LABELS: Record<string, string> = {
  grid: 'Grid',
  dca: 'DCA',
  trend_follower: 'Trend',
  hybrid: 'Hybrid',
  smc: 'SMC',
};

/** Tiny sparkline composed of 7 random-ish bars based on bot name (deterministic seed) */
function Sparkline({ profit, name }: { profit: number; name: string }) {
  // Generate pseudo-random heights seeded by bot name so they're stable across renders
  const seed = name.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const bars = Array.from({ length: 7 }, (_, i) => {
    const v = ((seed * (i + 1) * 17) % 40) + 10;
    return v;
  });
  const color = profit >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div className="flex items-end gap-0.5 h-8">
      {bars.map((h, i) => (
        <div
          key={i}
          className="w-1 rounded-sm opacity-60"
          style={{ height: `${h}%`, background: color }}
        />
      ))}
    </div>
  );
}

export function BotCard({ bot, onStart, onStop, onClick }: BotCardProps) {
  const profit = parseFloat(bot.total_profit);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-surface border border-border rounded-xl p-5 hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text">{bot.name}</h3>
        <Badge variant={statusVariant(bot.status)}>{bot.status}</Badge>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <Badge variant="info">{STRATEGY_LABELS[bot.strategy] || bot.strategy}</Badge>
        <span className="text-xs text-text-muted">{bot.symbol}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <p className="text-xs text-text-muted">PnL</p>
          <p className={`text-sm font-semibold ${profit >= 0 ? 'text-profit' : 'text-loss'}`}>
            {profit >= 0 ? '+' : ''}{profit.toFixed(2)}$
          </p>
        </div>
        <div>
          <p className="text-xs text-text-muted">Trades</p>
          <p className="text-sm font-semibold text-text">{bot.total_trades}</p>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <Sparkline profit={profit} name={bot.name} />
        <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
          {bot.status === 'running' ? (
            <Button variant="danger" size="sm" onClick={onStop}>Stop</Button>
          ) : (
            <Button variant="primary" size="sm" onClick={onStart}>Start</Button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
