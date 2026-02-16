import client from './client';

export interface BotListItem {
  name: string;
  strategy: string;
  symbol: string;
  status: string;
  total_trades: number;
  total_profit: string;
  active_positions: number;
}

export interface BotStatus {
  name: string;
  strategy: string;
  symbol: string;
  status: string;
  dry_run: boolean;
  uptime_seconds: number | null;
  total_trades: number;
  total_profit: string;
  unrealized_pnl: string;
  active_positions: number;
  open_orders: number;
  config: Record<string, unknown> | null;
}

export interface Position {
  symbol: string;
  side: string;
  size: string;
  entry_price: string;
  current_price: string | null;
  unrealized_pnl: string | null;
}

export interface PnL {
  total_realized_pnl: string;
  total_unrealized_pnl: string;
  total_fees: string;
  win_rate: number | null;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
}

export const botsApi = {
  list: (params?: { strategy?: string; status?: string; symbol?: string }) =>
    client.get<BotListItem[]>('/api/v1/bots', { params }),

  get: (name: string) =>
    client.get<BotStatus>(`/api/v1/bots/${name}`),

  start: (name: string) =>
    client.post(`/api/v1/bots/${name}/start`),

  stop: (name: string) =>
    client.post(`/api/v1/bots/${name}/stop`),

  pause: (name: string) =>
    client.post(`/api/v1/bots/${name}/pause`),

  resume: (name: string) =>
    client.post(`/api/v1/bots/${name}/resume`),

  emergencyStop: (name: string) =>
    client.post(`/api/v1/bots/${name}/emergency-stop`),

  getPositions: (name: string) =>
    client.get<Position[]>(`/api/v1/bots/${name}/positions`),

  getPnl: (name: string) =>
    client.get<PnL>(`/api/v1/bots/${name}/pnl`),
};
