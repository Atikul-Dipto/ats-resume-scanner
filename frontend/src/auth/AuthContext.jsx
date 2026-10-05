import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { auth, onUnauthorized, tokenStore } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // "checking" while a stored token is being validated, so pages that need
  // an account don't flash a sign-in prompt for a signed-in user.
  const [status, setStatus] = useState(() => (tokenStore.get() ? "checking" : "anonymous"));

  const logout = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  useEffect(() => onUnauthorized(logout), [logout]);

  useEffect(() => {
    if (status !== "checking") return;
    auth
      .me()
      .then((me) => {
        setUser(me);
        setStatus("authenticated");
      })
      .catch((err) => {
        // Keep the token on a network error (cold-starting backend); drop it on 401.
        if (err.status === 401) logout();
        else setStatus("anonymous");
      });
  }, [status, logout]);

  const signIn = useCallback(async (mode, email, password) => {
    const result = mode === "register" ? await auth.register(email, password) : await auth.login(email, password);
    tokenStore.set(result.access_token);
    setUser(result.user);
    setStatus("authenticated");
    return result.user;
  }, []);

  const value = useMemo(() => ({ user, status, signIn, logout }), [user, status, signIn, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
