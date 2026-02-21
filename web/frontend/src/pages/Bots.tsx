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
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

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

  const setLoading = (name: string, loading: boolean) =>
    setActionLoading((prev) => ({ ...prev, [name]: loading }));

  const handleStart = async (name: string) => {
    setLoading(name, true);
    try {
      await botsApi.start(name);
      toast(`Bot "${name}" started`, 'success');
      fetchBots();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail ?? `Failed to start "${name}"`, 'error');
    } finally {
      setLoading(name, false);
    }
  };

  const handleStop = async (name: string) => {
    setLoading(name, true);
    try {
      await botsApi.stop(name);
      toast(`Bot "${name}" stopped`, 'info');
      fetchBots();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail ?? `Failed to stop "${name}"`, 'error');
    } finally {
      setLoading(name, false);
    }
  };

  const handleDelete = async (name: string) => {
    setLoading(name, true);
    try {
      await botsApi.delete(name);
      toast(`Bot "${name}" deleted`, 'success');
      fetchBots();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail ?? `Failed to delete "${name}"`, 'error');
    } finally {
      setLoading(name, false);
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
              actionLoading={actionLoading[bot.name] ?? false}
              onStart={() => handleStart(bot.name)}
              onStop={() => handleStop(bot.name)}
              onDelete={() => handleDelete(bot.name)}
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
