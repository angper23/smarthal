// Dashboard screen — the main hub after login
// Shows camera status, the latest alert, and navigation buttons to all features
import { useNavigate } from "react-router";
import { Video, Clock, UserPlus, Bell, AlertCircle, CheckCircle } from "lucide-react";

export function DashboardScreen() {
  // useNavigate lets us send the user to any screen on button click
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Top header bar */}
      <div className="bg-white border-b-2 border-gray-300 p-4">
        <h1 className="text-2xl">SmartHal Dashboard</h1>
      </div>

      <div className="p-4 space-y-4">

        {/* Camera status card — hardcoded as Online for the prototype */}
        <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
          <h2 className="text-lg mb-3">Camera Status</h2>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-600" />
            <span className="text-green-600">Online</span>
          </div>
        </div>

        {/* Latest alert card — hardcoded mock data for the prototype */}
        <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
          <h2 className="text-lg mb-3">Latest Alert</h2>
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-orange-600 mt-1" />
            <div>
              <p className="mb-1">Unknown Individual Detected</p>
              <p className="text-sm text-gray-600">Today at 2:45 PM</p>
            </div>
          </div>
        </div>

        {/* Navigation buttons — each one takes the user to a different screen */}
        <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
          <h2 className="text-lg mb-4">Main Features</h2>
          <div className="space-y-3">

            {/* Live feed — main feature, opens webcam + face detection */}
            <button
              onClick={() => navigate("/live-feed")}
              className="w-full flex items-center gap-3 p-4 border-2 border-gray-300 rounded hover:bg-gray-100"
            >
              <Video className="w-6 h-6 text-gray-700" />
              <span>View Live Feed</span>
            </button>

            {/* Event history — shows a list of past detection events */}
            <button
              onClick={() => navigate("/event-history")}
              className="w-full flex items-center gap-3 p-4 border-2 border-gray-300 rounded hover:bg-gray-100"
            >
              <Clock className="w-6 h-6 text-gray-700" />
              <span>Event History</span>
            </button>

            {/* Register resident — mock form to add a known face */}
            <button
              onClick={() => navigate("/register-resident")}
              className="w-full flex items-center gap-3 p-4 border-2 border-gray-300 rounded hover:bg-gray-100"
            >
              <UserPlus className="w-6 h-6 text-gray-700" />
              <span>Register Resident</span>
            </button>

            {/* Alert settings — toggle notification preferences */}
            <button
              onClick={() => navigate("/alert-settings")}
              className="w-full flex items-center gap-3 p-4 border-2 border-gray-300 rounded hover:bg-gray-100"
            >
              <Bell className="w-6 h-6 text-gray-700" />
              <span>Alert Settings</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
