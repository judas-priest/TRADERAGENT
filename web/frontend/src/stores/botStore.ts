import { create } from 'zustand';
import { botsApi, type BotListItem } from '../api/bots';

interface BotState {
  bots: BotListItem[];
  isLoading: boolean;
  error: string | null;
  fetchBots: (filters?: { strategy?: string; status?: string }) => Promise<void>;
}

export const useBotStore = create<BotState>((set) => ({
  bots: [],
  isLoading: false,
  error: null,

  fetchBots: async (filters) => {
    set({ isLoading: true, error: null });
    try {
      const { data } = await botsApi.list(filters);
      set({ bots: data, isLoading: false });
    } catch (err) {
      set({ error: 'Failed to fetch bots', isLoading: false });
    }
  },
}));
