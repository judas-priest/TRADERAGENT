import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { botsApi } from '../api/bots';
import type { PnLDataPoint } from '../api/bots';
import { BotCard } from '../components/bots/BotCard';
import { CreateBotModal } from '../components/bots/CreateBotModal';
import { Button } from '../components/common/Button';
import { PageTransition } from '../components/common/PageTransition';
import { SkeletonBotCard } from '../components/common/Skeleton';
import { useToastStore } from '../components/common/Toast';
import { useBotStore } from '../stores/botStore';

export function Bots() {
  const { bots, isLoading, fetchBots } = useBotStore();
  const navigate = useNavigate();
  const toast = useToastStore((s) => s.add);
  const [createOpen, setCreateOpen] = useState(false);
  const [pnlHistories, setPnlHistories] = useState<Record<string, PnLDataPoint[]>>({});

  useEffect(() => {
    fetchBots();
  }, [fetchBots]);

  // Fetch PnL histories in parallel whenever the bots list changes.
  useEffect(() => {
    if (bots.length === 0) return;
    Promise.allSettled(
      bots.map((bot) =>
        botsApi.getPnlHistory(bot.name).then((res) => ({ name: bot.name, points: res.data.points }))
      )
    ).then((results) => {
      const histories: Record<string, PnLDataPoint[]> = {};
      for (const result of results) {
        if (result.status === 'fulfilled') {
          histories[result.value.name] = result.value.points;
        }
      }
      setPnlHistories(histories);
    });
  }, [bots]);

  const handleStart = async (name: string) => {
    try {
      await botsApi.start(name);
      toast(`Bot "${name}" started`, 'success');
      fetchBots();
    } catch {
      toast(`Failed to start "${name}"`, 'error');
    }
  };

  const handleStop = async (name: string) => {
    try {
      await botsApi.stop(name);
      toast(`Bot "${name}" stopped`, 'info');
      fetchBots();
    } catch {
      toast(`Failed to stop "${name}"`, 'error');
    }
  };

  if (isLoading) {
    return (
      <div>
        <div className="flex items-center justify-between mb-6">
          <div className="h-7 w-20 animate-pulse bg-border/50 rounded" />
          <div className="h-4 w-16 animate-pulse bg-border/50 rounded" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonBotCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <PageTransition>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-text font-[Manrope]">Bots</h2>
        <div className="flex items-center gap-3">
          <span className="text-sm text-text-muted">{bots.length} bot(s)</span>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            + Create Bot
          </Button>
        </div>
      </div>

      {bots.length === 0 ? (
        <div className="bg-surface border border-border rounded-xl p-12 text-center">
          <p className="text-text-muted mb-4">No bots configured yet</p>
          <Button onClick={() => setCreateOpen(true)}>+ Create your first bot</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {bots.map((bot) => (
            <BotCard
              key={bot.name}
              bot={bot}
              pnlHistory={pnlHistories[bot.name]}
              onStart={() => handleStart(bot.name)}
              onStop={() => handleStop(bot.name)}
              onClick={() => navigate(`/bots/${bot.name}`)}
            />
          ))}
        </div>
      )}

      <CreateBotModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={fetchBots}
      />
    </PageTransition>
  );
}
