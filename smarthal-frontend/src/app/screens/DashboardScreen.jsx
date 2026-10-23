// Dashboard screen — the main hub after login
// Shows camera status, the latest alert, and navigation buttons to all features
import { useNavigate } from "react-router";
import { Video, Clock, UserPlus, Bell, AlertCircle, CheckCircle, LogOut, KeyRound } from "lucide-react";
import { useAuth } from "../AuthContext.jsx";

export function DashboardScreen() {
  // useNavigate lets us send the user to any screen on button click
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen">

      {/* Top header bar */}
      <div className="bg-window border-b-2 border-border p-4 flex items-center gap-3">
        <h1 className="text-bgtext">SmartHal Dashboard</h1>
        <div className="ml-auto flex items-center gap-3">
          {user && <span className="text-sm text-bgtext">{user.username}</span>}
          <button
            onClick={() => navigate("/change-password")}
            className="flex items-center gap-1 text-sm bg-panel border-2 border-border rounded px-3 py-1 hover:bg-gray-100"
          >
            <KeyRound className="w-4 h-4" />
            Change Password
          </button>
          {/* Ends the session on the backend; the route guard then sends us to /login */}
          <button
            onClick={logout}
            className="flex items-center gap-1 text-sm bg-panel border-2 border-border rounded px-3 py-1 hover:bg-gray-100"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </div>

      <div className="p-4 space-y-4">

        {/* Camera status card — hardcoded as Online for the prototype */}
        <div className="bg-window border-2 border-border rounded-lg p-4">
          <h2 className="text-bgtext mb-3">Camera Status</h2>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-statusgood" />
            <span className="text-statusgood">Online</span>
          </div>
        </div>

        {/* Latest alert card — hardcoded mock data for the prototype */}
        <div className="bg-window border-2 border-border rounded-lg p-4">
          <h2 className="text-bgtext mb-3">Latest Alert</h2>
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-statuscheck mt-1" />
            <div>
              <p className="mb-1 text-statuscheck">Unknown Individual Detected</p>
              <p className="text-sm text-bgtextb">Today at 2:45 PM</p>
            </div>
          </div>
        </div>

        {/* Navigation buttons — each one takes the user to a different screen */}
        <div className="bg-window border-2 border-border rounded-lg p-4">
          <h2 className="text-bgtext mb-4">Main Features</h2>
          <div className="space-y-3">

            {/* Live feed — main feature, opens webcam + face detection */}
            <button
              onClick={() => navigate("/live-feed")}
              className="bg-panel w-full flex items-center gap-3 p-4 border-2 border-border rounded hover:bg-border cursor-pointer"
            >
              <Video className="w-6 h-6 text-wintext" />
              <span>View Live Feed</span>
            </button>

            {/* Event history — shows a list of past detection events */}
            <button
              onClick={() => navigate("/event-history")}
              className="bg-panel w-full flex items-center gap-3 p-4 border-2 border-border rounded hover:bg-border cursor-pointer"
            >
              <Clock className="w-6 h-6 text-wintext" />
              <span>Event History</span>
            </button>

            {/* Register resident — mock form to add a known face */}
            <button
              onClick={() => navigate("/register-resident")}
              className="bg-panel w-full flex items-center gap-3 p-4 border-2 border-border rounded hover:bg-border cursor-pointer"
            >
              <UserPlus className="w-6 h-6 text-wintext" />
              <span>Register Resident</span>
            </button>

            {/* Alert settings — toggle notification preferences */}
            <button
              onClick={() => navigate("/alert-settings")}
              className="bg-panel w-full flex items-center gap-3 p-4 border-2 border-border rounded hover:bg-border cursor-pointer"
            >
              <Bell className="w-6 h-6 text-wintext" />
              <span>Alert Settings</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
