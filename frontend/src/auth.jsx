import { createContext, useContext, useState } from "react";

const AuthCtx = createContext(null);

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("sutra_user"));
  } catch {
    return null;
  }
}

export const getToken = () => getStoredUser()?.token ?? null;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser());

  const login = async (username, password) => {
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) throw new Error("Invalid credentials");
    const u = await r.json();
    localStorage.setItem("sutra_user", JSON.stringify(u));
    setUser(u);
    return u;
  };

  const logout = () => {
    fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    localStorage.removeItem("sutra_user");
    setUser(null);
  };

  const canOperate = user && (user.role === "admin" || user.role === "operator");

  return (
    <AuthCtx.Provider value={{ user, login, logout, canOperate }}>{children}</AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
