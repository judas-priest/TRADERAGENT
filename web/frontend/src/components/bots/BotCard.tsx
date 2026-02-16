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
        <Badge variant="info">{bot.strategy}</Badge>
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
