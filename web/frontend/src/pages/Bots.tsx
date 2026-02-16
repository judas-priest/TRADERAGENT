import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BotCard } from '../components/bots/BotCard';
import { Spinner } from '../components/common/Spinner';
import { useBotStore } from '../stores/botStore';
import { botsApi } from '../api/bots';

export function Bots() {
  const { bots, isLoading, fetchBots } = useBotStore();
  const navigate = useNavigate();

  useEffect(() => {
    fetchBots();
  }, [fetchBots]);

  const handleStart = async (name: string) => {
    await botsApi.start(name);
    fetchBots();
  };

  const handleStop = async (name: string) => {
    await botsApi.stop(name);
    fetchBots();
  };

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-text font-[Manrope]">Bots</h2>
        <span className="text-sm text-text-muted">{bots.length} bot(s)</span>
      </div>

      {bots.length === 0 ? (
        <div className="bg-surface border border-border rounded-xl p-12 text-center">
          <p className="text-text-muted">No bots configured yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {bots.map((bot) => (
            <BotCard
              key={bot.name}
              bot={bot}
              onStart={() => handleStart(bot.name)}
              onStop={() => handleStop(bot.name)}
              onClick={() => navigate(`/bots/${bot.name}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
