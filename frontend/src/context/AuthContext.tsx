import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import type { User } from '../types';
import { api } from '../api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
  isAdmin: boolean;
  isPlanner: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Access token stored IN MEMORY ONLY — never in localStorage
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearAuth = useCallback(() => {
    setToken(null);
    setUser(null);
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const scheduleTokenRefresh = useCallback((accessToken: string) => {
    // Parse JWT expiry and refresh 60 seconds before it expires
    try {
      const payload = JSON.parse(atob(accessToken.split('.')[1]));
      const expiresAt = payload.exp * 1000; // ms
      const refreshAt = expiresAt - Date.now() - 60_000; // 60s before expiry
      const delay = Math.max(refreshAt, 5_000); // minimum 5s

      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = setTimeout(async () => {
        try {
          const res = await api.auth.refresh();
          setToken(res.access_token);
          scheduleTokenRefresh(res.access_token);
        } catch {
          clearAuth();
        }
      }, delay);
    } catch {
      // Can't parse JWT — don't schedule
    }
  }, [clearAuth]);

  // On mount: try to get a new access token via the refresh cookie
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.auth.refresh();
        if (!cancelled) {
          setToken(res.access_token);
          // Fetch user profile with the new access token
          const me = await api.auth.getMe(res.access_token);
          if (!cancelled) {
            setUser(me);
            scheduleTokenRefresh(res.access_token);
          }
        }
      } catch {
        if (!cancelled) clearAuth();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = async (email: string, pass: string) => {
    const res = await api.auth.login(email, pass);
    setToken(res.access_token);
    setUser(res.user);
    scheduleTokenRefresh(res.access_token);
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } catch {
      // Ignore logout errors
    }
    clearAuth();
  };

  const isAdmin = user?.role === 'admin';
  const isPlanner = user?.role === 'planner' || user?.role === 'admin';

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, isAdmin, isPlanner }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
