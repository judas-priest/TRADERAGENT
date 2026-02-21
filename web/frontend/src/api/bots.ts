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

export interface BotCreateRequest {
  name: string;
  symbol: string;
  strategy: string;
  exchange_id: string;
  credentials_name: string;
  dry_run: boolean;
  risk_management: {
    max_position_size: number;
  };
  grid?: Record<string, unknown>;
  dca?: Record<string, unknown>;
  trend_follower?: Record<string, unknown>;
  smc?: Record<string, unknown>;
}

export interface BotCreateResponse {
  name: string;
  symbol: string;
  strategy: string;
  dry_run: boolean;
  message: string;
}

export interface BotUpdateRequest {
  dry_run?: boolean;
  risk_management?: { max_position_size: number };
  grid?: Record<string, unknown>;
  dca?: Record<string, unknown>;
  trend_follower?: Record<string, unknown>;
}

export interface Trade {
  id: number;
  symbol: string;
  side: string;
  price: string;
  amount: string;
  fee: string;
  profit: string | null;
  executed_at: string;
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

export interface PnLDataPoint {
  timestamp: number;
  value: number;
}

export interface PnLHistory {
  points: PnLDataPoint[];
}

export const botsApi = {
  create: (data: BotCreateRequest) =>
    client.post<BotCreateResponse>('/api/v1/bots', data),

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

  update: (name: string, data: BotUpdateRequest) =>
    client.put(`/api/v1/bots/${name}`, data),

  delete: (name: string) =>
    client.delete(`/api/v1/bots/${name}`),

  getPnl: (name: string) =>
    client.get<PnL>(`/api/v1/bots/${name}/pnl`),

  getPnlHistory: (name: string, period: string = '7d') =>
    client.get<PnLHistory>(`/api/v1/bots/${name}/pnl/history`, { params: { period } }),
};
