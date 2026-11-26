import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, getStoredToken, setStoredToken } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(getStoredToken()));
  const [favorites, setFavorites] = useState([]);
  const [history, setHistory] = useState({ routes: [], sessions: [] });

  const refreshUserData = useCallback(async () => {
    if (!getStoredToken()) {
      setUser(null);
      setFavorites([]);
      setHistory({ routes: [], sessions: [] });
      setLoading(false);
      return;
    }

    try {
      const profile = await api.getProfile();
      setUser(profile);
      const [favRes, histRes] = await Promise.all([
        api.getFavorites().catch(() => ({ items: [] })),
        api.getHistory().catch(() => ({ routes: [], sessions: [] })),
      ]);
      setFavorites(favRes.items || []);
      setHistory({
        routes: histRes.routes || [],
        sessions: histRes.sessions || [],
      });
    } catch {
      setStoredToken(null);
      setUser(null);
      setFavorites([]);
      setHistory({ routes: [], sessions: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUserData();
  }, [refreshUserData]);

  const login = useCallback(
    async (email, password) => {
      const res = await api.login({ email, password });
      setStoredToken(res.access_token);
      setUser(res.user);
      await refreshUserData();
      return res.user;
    },
    [refreshUserData]
  );

  const register = useCallback(
    async (fullName, email, password) => {
      const res = await api.register({ full_name: fullName, email, password });
      setStoredToken(res.access_token);
      setUser(res.user);
      await refreshUserData();
      return res.user;
    },
    [refreshUserData]
  );

  const logout = useCallback(() => {
    setStoredToken(null);
    setUser(null);
    setFavorites([]);
    setHistory({ routes: [], sessions: [] });
  }, []);

  const addFavorite = useCallback(
    async (place) => {
      const saved = await api.addFavorite(place);
      setFavorites((prev) => [saved, ...prev]);
      return saved;
    },
    []
  );

  const removeFavorite = useCallback(async (favoriteId) => {
    await api.deleteFavorite(favoriteId);
    setFavorites((prev) => prev.filter((item) => item.id !== favoriteId));
  }, []);

  const value = {
    user,
    loading,
    isAuthenticated: Boolean(user),
    favorites,
    history,
    login,
    register,
    logout,
    refreshUserData,
    addFavorite,
    removeFavorite,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return ctx;
}
