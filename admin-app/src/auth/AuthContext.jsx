import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, setCsrfToken } from "../api/client.js";


const AuthContext = createContext(null);


export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recoveryCodes, setRecoveryCodes] = useState(null);

  const restoreSession = useCallback(async () => {
    try {
      const current = await api("/api/admin/session");
      setCsrfToken(current.csrf_token);
      setSession(current);
    } catch {
      setSession(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    restoreSession();
    const expired = () => setSession(null);
    window.addEventListener("ninesense:session-expired", expired);
    return () => window.removeEventListener("ninesense:session-expired", expired);
  }, [restoreSession]);

  const startLogin = useCallback((username, password) => api("/api/admin/session", {
    method: "POST",
    body: JSON.stringify({ username, password })
  }), []);

  const completeMfa = useCallback(async (challengeToken, code) => {
    const authenticated = await api("/api/admin/session/mfa", {
      method: "POST",
      body: JSON.stringify({ challenge_token: challengeToken, code })
    });
    setCsrfToken(authenticated.csrf_token);
    setSession(authenticated);
    setRecoveryCodes(authenticated.recovery_codes || null);
    return authenticated;
  }, []);

  const value = useMemo(() => ({
    session,
    loading,
    recoveryCodes,
    startLogin,
    completeMfa,
    acknowledgeRecoveryCodes: () => setRecoveryCodes(null)
  }), [session, loading, recoveryCodes, startLogin, completeMfa]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}


export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
