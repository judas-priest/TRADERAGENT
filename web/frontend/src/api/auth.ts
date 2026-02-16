import client from './client';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export const authApi = {
  login: (data: LoginRequest) =>
    client.post<TokenResponse>('/api/v1/auth/login', data),

  register: (data: RegisterRequest) =>
    client.post<User>('/api/v1/auth/register', data),

  refresh: (refreshToken: string) =>
    client.post<TokenResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken }),

  logout: (refreshToken: string) =>
    client.post('/api/v1/auth/logout', { refresh_token: refreshToken }),

  getMe: () =>
    client.get<User>('/api/v1/auth/me'),
};
