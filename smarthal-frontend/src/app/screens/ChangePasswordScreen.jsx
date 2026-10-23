// Change Password screen — lets the logged-in user pick a new password
// (POST /change-password). The current password is required, so someone
// who finds the app already logged in can't take over the account. After a
// change, the backend signs out every other login of this account; this
// one stays logged in
import { useState } from "react";
import { useNavigate } from "react-router";
import { ArrowLeft, AlertTriangle, CheckCircle } from "lucide-react";
import { apiFetch, NetworkError } from "../api.js";

/** Change Password screen (/change-password). */
export function ChangePasswordScreen() {
  const navigate = useNavigate();

  // Track what the user types into the form fields
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  // Whether the request is in flight — disables the form meanwhile
  const [loading, setLoading] = useState(false);

  // Message shown above the form when the change fails, or null
  const [error, setError] = useState(null);

  // Whether the password was changed successfully
  const [done, setDone] = useState(false);

  // Send the change to the backend and show the result; the fields are always cleared afterwards
  const handleSubmit = async (e) => {
    e.preventDefault(); // Stop the page from refreshing on form submit
    if (newPassword !== confirm) {
      setError("New passwords don't match.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/change-password", {
        method: "POST",
        body: { current_password: currentPassword, new_password: newPassword },
      });
      if (res.ok) {
        setDone(true);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(
          res.status === 429
            ? "Too many attempts. Try again in a few minutes."
            : data.error || "Couldn't change the password."
        );
      }
    } catch (err) {
      setError(err instanceof NetworkError ? "Can't reach the server." : "Something went wrong. Try again.");
    }
    // Never leave passwords sitting in the form
    setCurrentPassword("");
    setNewPassword("");
    setConfirm("");
    setLoading(false);
  };

  const inputClass = "w-full px-4 py-2 border-2 border-gray-300 rounded bg-panel";

  return (
    <div className="min-h-screen bg-background">

      {/* Header with back button */}
      <div className="bg-window border-b-2 border-border p-4 flex items-center gap-3">
        <button onClick={() => navigate("/dashboard")} className="p-1 hover:bg-gray-100 rounded">
          <ArrowLeft className="w-6 h-6 text-bgtext" />
        </button>
        <h1 className="text-2xl text-bgtext">Change Password</h1>
      </div>

      <div className="p-4 space-y-4">

        {/* Success — shown instead of the form */}
        {done ? (
          <div className="bg-window border-2 border-border rounded-lg p-4 space-y-3">
            <p className="flex items-center gap-2 text-statusgood font-medium">
              <CheckCircle className="w-5 h-5" />
              Password changed
            </p>
            <p className="text-sm text-bgtext">
              Use your new password next time you log in. Any other device that was
              logged in to this account has been signed out.
            </p>
            <button
              onClick={() => navigate("/dashboard")}
              className="w-full py-3 bg-panel text-wintext rounded border-2 border-border hover:bg-border"
            >
              Back to Dashboard
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-window border-2 border-gray-300 rounded-lg p-4 space-y-4">

            {/* Error message — wrong current password, rule broken, rate limited, or backend down */}
            {error && (
              <div role="alert" className="bg-red-50 border-2 border-red-300 rounded p-3 flex items-start gap-2 text-sm text-red-800">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-red-600" />
                <span>{error}</span>
              </div>
            )}

            <div>
              <label htmlFor="current-password" className="block text-sm mb-2 text-bgtext">Current password</label>
              <input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className={inputClass}
                autoComplete="current-password"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="new-password" className="block text-sm mb-2 text-bgtext">New password</label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className={inputClass}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                minLength={8}
                required
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="confirm-password" className="block text-sm mb-2 text-bgtext">Confirm new password</label>
              <input
                id="confirm-password"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={inputClass}
                autoComplete="new-password"
                required
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-panel text-wintext rounded border-2 border-border hover:bg-border disabled:opacity-60 disabled:cursor-wait"
            >
              {loading ? "Changing…" : "Change Password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
