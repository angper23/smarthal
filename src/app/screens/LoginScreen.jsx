// Login screen — the first screen the user sees when opening the app
// This is a mock login — any username and password will work, no real auth
import { useState } from "react";
import { useNavigate } from "react-router";
import { Shield } from "lucide-react";

export function LoginScreen() {
  // useNavigate lets us programmatically change the page
  const navigate = useNavigate();

  // Track what the user types into the form fields
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // When the form is submitted, skip validation and go straight to the dashboard
  const handleLogin = (e) => {
    e.preventDefault(); // Stop the page from refreshing on form submit
    navigate("/dashboard");
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">

        {/* App logo and title */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Shield className="w-16 h-16 text-gray-700" />
          </div>
          <h1 className="text-3xl mb-2">SmartHal</h1>
          <p className="text-gray-600">Home Security Monitoring</p>
        </div>

        {/* Login form */}
        <div className="bg-white border-2 border-gray-300 rounded-lg p-6">
          <form onSubmit={handleLogin} className="space-y-4">

            {/* Username field */}
            <div>
              <label htmlFor="username" className="block text-sm mb-2 text-gray-700">
                Email or Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2 border-2 border-gray-300 rounded bg-white"
                placeholder="Enter email or username"
              />
            </div>

            {/* Password field */}
            <div>
              <label htmlFor="password" className="block text-sm mb-2 text-gray-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2 border-2 border-gray-300 rounded bg-white"
                placeholder="Enter password"
              />
            </div>

            {/* Submit button — navigates to dashboard on click */}
            <button
              type="submit"
              className="w-full py-3 bg-gray-800 text-white rounded border-2 border-gray-800 hover:bg-gray-700"
            >
              Login
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
