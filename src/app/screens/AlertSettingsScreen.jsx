// Alert Settings screen — lets the user configure notification preferences
// This is a mock UI — settings are stored in React state only, nothing is saved permanently
import { useState } from "react";
import { useNavigate } from "react-router";
import { ArrowLeft } from "lucide-react";

export function AlertSettingsScreen() {
  const navigate = useNavigate();

  // Master toggle — if false, all alert types are disabled
  const [alertsEnabled, setAlertsEnabled] = useState(true);

  // Whether to receive push notifications on this device
  const [pushNotifications, setPushNotifications] = useState(true);

  // Whether to receive email notifications
  const [emailNotifications, setEmailNotifications] = useState(false);

  // Mock save — shows an alert and returns to the dashboard
  const handleSave = (e) => {
    e.preventDefault(); // Stop page from refreshing on form submit
    alert("Alert settings saved successfully!");
    navigate("/dashboard");
  };

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Header with back button */}
      <div className="bg-white border-b-2 border-gray-300 p-4 flex items-center gap-3">
        <button onClick={() => navigate("/dashboard")} className="p-1 hover:bg-gray-100 rounded">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-2xl">Alert Settings</h1>
      </div>

      <div className="p-4">
        <form onSubmit={handleSave} className="space-y-4">

          {/* Master alerts toggle — controls whether any alerts are sent at all */}
          <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="mb-1">Enable Alerts</p>
                <p className="text-sm text-gray-600">Receive notifications for detected events</p>
              </div>
              {/* Custom toggle switch — visually slides when clicked */}
              <button
                type="button"
                onClick={() => setAlertsEnabled(!alertsEnabled)}
                className={`relative w-14 h-8 rounded-full border-2 transition-colors ${
                  alertsEnabled ? "bg-gray-800 border-gray-800" : "bg-gray-200 border-gray-300"
                }`}
              >
                {/* The sliding circle inside the toggle */}
                <span
                  className={`block w-6 h-6 bg-white rounded-full transition-transform ${
                    alertsEnabled ? "translate-x-6" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Alert type toggles — greyed out if master alerts are disabled */}
          <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
            <h2 className="text-lg mb-4">Alert Types</h2>

            <div className="space-y-4">

              {/* Push notification toggle */}
              <div className="flex items-center justify-between pb-4 border-b-2 border-gray-200">
                <div>
                  <p className="mb-1">Push Notifications</p>
                  <p className="text-sm text-gray-600">Receive alerts on this device</p>
                </div>
                {/* disabled prop greys it out when master alerts are off */}
                <input
                  type="checkbox"
                  checked={pushNotifications}
                  onChange={(e) => setPushNotifications(e.target.checked)}
                  className="w-5 h-5 border-2 border-gray-300 rounded"
                  disabled={!alertsEnabled}
                />
              </div>

              {/* Email notification toggle */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="mb-1">Email Notifications</p>
                  <p className="text-sm text-gray-600">Receive alerts via email</p>
                </div>
                <input
                  type="checkbox"
                  checked={emailNotifications}
                  onChange={(e) => setEmailNotifications(e.target.checked)}
                  className="w-5 h-5 border-2 border-gray-300 rounded"
                  disabled={!alertsEnabled}
                />
              </div>
            </div>
          </div>

          {/* Email address input — only shown if email notifications are turned on */}
          {emailNotifications && alertsEnabled && (
            <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
              <label htmlFor="email" className="block text-sm mb-2 text-gray-700">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                className="w-full px-4 py-2 border-2 border-gray-300 rounded bg-white"
                placeholder="Enter email address"
              />
            </div>
          )}

          {/* Save button — triggers handleSave */}
          <button
            type="submit"
            className="w-full py-3 bg-gray-800 text-white rounded border-2 border-gray-800 hover:bg-gray-700"
          >
            Save Settings
          </button>
        </form>
      </div>
    </div>
  );
}
