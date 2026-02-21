import { motion } from 'framer-motion';
import type { BotListItem, PnLDataPoint } from '../../api/bots';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { PnLSparkline } from './PnLSparkline';

interface BotCardProps {
  bot: BotListItem;
  pnlHistory?: PnLDataPoint[];
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

const strategyVariant = (s: string) => {
  switch (s.toLowerCase()) {
    case 'grid': return 'success' as const;
    case 'dca': return 'warning' as const;
    case 'trend_follower':
    case 'trend': return 'info' as const;
    case 'smc': return 'error' as const;
    case 'hybrid': return 'default' as const;
    default: return 'info' as const;
  }
};

export function BotCard({ bot, pnlHistory, onStart, onStop, onClick }: BotCardProps) {
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
        <Badge variant={strategyVariant(bot.strategy)}>{bot.strategy}</Badge>
        <span className="text-xs text-text-muted">{bot.symbol}</span>
      </div>

      <div className="flex items-end justify-between mb-4">
        <div className="grid grid-cols-2 gap-3 flex-1">
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
        <div className="ml-3 flex-shrink-0">
          <PnLSparkline points={pnlHistory ?? []} />
        </div>
      </div>

      <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
        {bot.status === 'running' ? (
          <Button variant="danger" size="sm" onClick={onStop}>Stop</Button>
        ) : (
          <Button variant="primary" size="sm" onClick={onStart}>Start</Button>
        )}
      </div>
    </motion.div>
  );
}
