// Auth state shared by every screen: the login token and the logged-in user
// Stored in sessionStorage so a page refresh keeps you logged in, but
// closing the tab (or opening a new one) doesn't
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router";
import { apiFetch, NetworkError, onUnauthorized, setApiToken } from "./api.js";

const STORAGE_KEY = "smarthal.auth";

const AuthContext = createContext(null);

// sessionStorage can throw (private mode, blocked storage) — treat any
// failure as "nothing stored" rather than crashing the app
function loadStored() {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(STORAGE_KEY));
    return parsed && parsed.token ? parsed : null;
  } catch {
    return null;
  }
}

// Save {token, user} to sessionStorage (or clear it when auth is null)
function saveStored(auth) {
  try {
    if (auth) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Not fatal — the session just won't survive a refresh
  }
}

/**
 * Wraps the app and shares login state with every screen (read it with useAuth()).
 * Holds the token and user, restores them after a page refresh, and logs out on any 401.
 */
export function AuthProvider({ children }) {
  // { token, user } or null when logged out
  const [auth, setAuth] = useState(() => {
    const stored = loadStored();
    setApiToken(stored?.token ?? null);
    return stored;
  });

  // Whether a token loaded from storage has been confirmed with GET /me yet
  const [validated, setValidated] = useState(() => !auth);

  // Forget the token everywhere (memory, api.js, sessionStorage); the route guard then shows /login
  const clearSession = useCallback(() => {
    setApiToken(null);
    saveStored(null);
    setAuth(null);
  }, []);

  // Any 401 on an authenticated request means the session is gone
  useEffect(() => {
    onUnauthorized(clearSession);
  }, [clearSession]);

  // On load, check that a stored token is still valid (the backend keeps
  // sessions in memory, so a backend restart invalidates every token)
  useEffect(() => {
    if (validated) return;
    let cancelled = false;
    apiFetch("/me")
      .then(async (res) => {
        if (cancelled || !res.ok) return; // a 401 already cleared the session
        const { user } = await res.json();
        setAuth((prev) => (prev ? { ...prev, user } : prev));
      })
      .catch((err) => {
        // Backend unreachable: keep the token and let screens show their
        // own "can't reach server" state; the next real request re-checks it
        if (!(err instanceof NetworkError)) throw err;
      })
      .finally(() => {
        if (!cancelled) setValidated(true);
      });
    return () => {
      cancelled = true;
    };
  }, [validated]);

  // Called by LoginScreen after a successful POST /login: remember the token and user
  const login = useCallback((token, user) => {
    setApiToken(token);
    saveStored({ token, user });
    setAuth({ token, user });
    setValidated(true);
  }, []);

  // Logout button: ask the backend to end the session, then forget the token here
  const logout = useCallback(async () => {
    try {
      await apiFetch("/logout", { method: "POST" });
    } catch {
      // Even if the backend is unreachable, forget the token locally
    }
    clearSession();
  }, [clearSession]);

  const value = {
    token: auth?.token ?? null,
    user: auth?.user ?? null,
    validated,
    login,
    logout,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Hook for screens: returns { token, user, validated, login, logout }. */
export function useAuth() {
  return useContext(AuthContext);
}

// Route guard — wraps every screen except /login
// No token means the user is sent to /login
export function RequireAuth() {
  const { token, validated } = useAuth();
  const { pathname } = useLocation();

  // Most screens are still mocked and never call the backend, so check the
  // session on every navigation — otherwise an idled-out session would only
  // be noticed on the Live Feed screen. A 401 logs out via apiFetch
  useEffect(() => {
    if (!token || !validated) return;
    apiFetch("/me").catch(() => {});
  }, [pathname, token, validated]);

  if (!token) return <Navigate to="/login" replace />;
  if (!validated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-600">
        Checking session…
      </div>
    );
  }
  return <Outlet />;
}
