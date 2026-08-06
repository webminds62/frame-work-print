import React, { createContext, useContext, useEffect, useState } from "react";
import { storage } from "@/src/utils/storage";
import { api, TOKEN_KEY } from "@/src/api";

type User = { id: string; email: string; name?: string; is_admin?: boolean };

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  appleLogin: (identityToken: string, name?: string, email?: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState>({} as AuthState);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await storage.secureGet<string>(TOKEN_KEY, "");
      if (token) {
        try {
          setUser(await api.me());
        } catch {
          await storage.secureRemove(TOKEN_KEY);
        }
      }
      setLoading(false);
    })();
  }, []);

  const persist = async (res: { token: string; user: User }) => {
    await storage.secureSet(TOKEN_KEY, res.token);
    setUser(res.user);
  };

  const login = async (email: string, password: string) => persist(await api.login(email, password));
  const register = async (email: string, password: string, name?: string) =>
    persist(await api.register(email, password, name));
  const appleLogin = async (identityToken: string, name?: string, email?: string) =>
    persist(await api.appleLogin(identityToken, name, email));
  const logout = async () => {
    await storage.secureRemove(TOKEN_KEY);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, appleLogin, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
