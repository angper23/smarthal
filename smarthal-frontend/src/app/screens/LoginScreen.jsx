// Login screen — the first screen the user sees when opening the app
// Collin's design, with the real login (POST /login) wired back in
import { useState } from "react";
import { Navigate, useNavigate } from "react-router";
import { AlertTriangle } from "lucide-react";
import { apiFetch, NetworkError } from "../api.js";
import { useAuth } from "../AuthContext.jsx";

export function LoginScreen() {
  // useNavigate lets us programmatically change the page
  const navigate = useNavigate();
  const { token, login } = useAuth();

  // Track what the user types into the form fields
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Whether a login request is in flight — disables the form meanwhile
  const [loading, setLoading] = useState(false);

  // Message shown above the form when login fails, or null
  const [error, setError] = useState(null);

  // When the form is submitted, ask the backend to check the credentials
  const handleLogin = async (e) => {
    e.preventDefault(); // Stop the page from refreshing on form submit
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/login", {
        method: "POST",
        body: { username, password },
      });
      if (res.ok) {
        const data = await res.json();
        login(data.token, data.user);
        navigate("/dashboard", { replace: true });
        return;
      }
      // Same message for unknown user and wrong password, on purpose — it
      // shouldn't reveal which usernames exist
      setError(
        res.status === 429
          ? "Too many attempts. Try again in a few minutes."
          : "Invalid username or password"
      );
    } catch (err) {
      setError(err instanceof NetworkError ? "Can't reach the server." : "Something went wrong. Try again.");
    }
    setPassword("");
    setLoading(false);
  };

  // Already logged in (e.g. came back to /login) — skip straight to the dashboard
  if (token) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">

        {/* App logo and title */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <img className="w-48 h-48 object-contain" src="img/Smart_Hal_Logo.png" />
          </div>
          <h1 className="text-bgtext mb-2">SmartHal</h1>
          <p className="text-bgtextb">Home Security Monitoring</p>
        </div>

        {/* Login form */}
        <div className="bg-window border-2 border-border rounded p-6">
          <form onSubmit={handleLogin} className="space-y-4">

            {/* Error message — wrong credentials, rate limited, or backend down */}
            {error && (
              <div role="alert" className="bg-panel border-2 border-statusrisk rounded p-3 flex items-start gap-2 text-sm text-wintext">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-statusrisk" />
                <span>{error}</span>
              </div>
            )}

            {/* Username field */}
            <div>
              <label htmlFor="username" className="block text-bgtext mb-2">
                Email or Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                disabled={loading}
                className="w-full px-4 py-2 border-2 border-border rounded bg-panel"
                placeholder="Enter Email or Username"
              />
            </div>

            {/* Password field */}
            <div>
              <label htmlFor="password" className="block text-sm mb-2 text-bgtext">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                disabled={loading}
                className="w-full px-4 py-2 border-2 border-border rounded bg-panel"
                placeholder="Enter Password"
              />
            </div>

            {/* Submit button — disabled while the login request is in flight */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-panel text-wintext rounded border-2 border-border hover:bg-border cursor-pointer disabled:opacity-60 disabled:cursor-wait"
            >
              {loading ? "Logging in…" : "Login"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
