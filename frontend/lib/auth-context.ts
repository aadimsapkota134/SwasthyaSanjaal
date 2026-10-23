"use client";

import React, {
  createContext, useContext, useEffect, useState, useCallback, useRef, ReactNode,
} from "react";
import { login, logout, getCurrentUser } from "@/lib/api";
import type { UserResponse } from "@/lib/contracts";

const AuthContext = createContext<{
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
} | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const didMount = useRef(false);

  const refreshUser = useCallback(async () => {
    try {
      const current = await getCurrentUser();
      setUser(current);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!didMount.current) {
      didMount.current = true;
      refreshUser();
    }
  }, [refreshUser, didMount]);

  const doLogin = useCallback(
    async (email: string, password: string) => {
      const result = await login(email, password);
      if (result) {
        setUser(result.user);
        return true;
      }
      setUser(null);
      return false;
    },
    []
  );

  const doLogout = useCallback(async () => {
    await logout();
    setUser(null);
  }, []);

  const value = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login: doLogin,
    logout: doLogout,
    refreshUser,
  };

  return React.createElement(AuthContext.Provider, { value }, children);
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
