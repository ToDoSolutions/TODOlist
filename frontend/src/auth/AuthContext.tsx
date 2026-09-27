import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { authApi } from "../api/auth";
import { tokenStorage } from "../api/client";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, totpCode?: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  saveTokens: (access: string, refresh: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // La sesión puede vivir solo en cookies httpOnly: siempre intentamos me()
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => tokenStorage.clear())
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string, totpCode?: string) => {
    await authApi.login(email, password, totpCode);
    const me = await authApi.me();
    setUser(me);
  };

  const register = async (email: string, username: string, password: string) => {
    await authApi.register({
      email,
      username,
      password,
      password2: password,
    });
    await login(email, password);
  };

  const logout = () => {
    authApi.logout();
    setUser(null);
  };

  const saveTokens = async (access: string, refresh: string) => {
    tokenStorage.set(access, refresh);
    const me = await authApi.me();
    setUser(me);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, saveTokens }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
