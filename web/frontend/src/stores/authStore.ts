import { create } from 'zustand';
import { authApi, type User } from '../api/auth';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: false,

  login: async (username, password) => {
    set({ isLoading: true });
    try {
      const { data } = await authApi.login({ username, password });
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      const { data: user } = await authApi.getMe();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ isLoading: false });
      throw new Error('Login failed');
    }
  },

  logout: async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch {
        // ignore
      }
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      set({ isAuthenticated: false, user: null });
      return;
    }
    try {
      const { data: user } = await authApi.getMe();
      set({ user, isAuthenticated: true });
    } catch {
      set({ isAuthenticated: false, user: null });
    }
  },
}));
