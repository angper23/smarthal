// Event History screen — shows a list of all past detection events
// All data is hardcoded mock data for the prototype (no real database)
import { useNavigate } from "react-router";
import { ArrowLeft, AlertCircle, UserCheck } from "lucide-react";

// Mock event data — in a real app this would come from a database
const mockEvents = [
  {
    id: "1",
    timestamp: "March 10, 2026 at 2:45 PM",
    classification: "Unknown",
    description: "Unknown individual detected at front door",
  },
  {
    id: "2",
    timestamp: "March 10, 2026 at 10:30 AM",
    classification: "Resident",
    description: "Resident identified: John Smith",
  },
  {
    id: "3",
    timestamp: "March 9, 2026 at 6:15 PM",
    classification: "Unknown",
    description: "Unknown individual detected at front door",
  },
  {
    id: "4",
    timestamp: "March 9, 2026 at 3:22 PM",
    classification: "Resident",
    description: "Resident identified: Sarah Johnson",
  },
  {
    id: "5",
    timestamp: "March 9, 2026 at 8:05 AM",
    classification: "Resident",
    description: "Resident identified: John Smith",
  },
  {
    id: "6",
    timestamp: "March 8, 2026 at 5:40 PM",
    classification: "Unknown",
    description: "Unknown individual detected at front door",
  },
];

export function EventHistoryScreen() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Header with back button */}
      <div className="bg-white border-b-2 border-gray-300 p-4 flex items-center gap-3">
        <button onClick={() => navigate("/dashboard")} className="p-1 hover:bg-gray-100 rounded">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-2xl">Event History</h1>
      </div>

      <div className="p-4">
        {/* Render one card per event — clicking navigates to the detail view */}
        <div className="space-y-3">
          {mockEvents.map((event) => (
            <button
              key={event.id}
              onClick={() => navigate(`/event-detail/${event.id}`)} // Pass event ID in URL
              className="w-full bg-white border-2 border-gray-300 rounded-lg p-4 hover:bg-gray-100 text-left"
            >
              <div className="flex items-start gap-3">
                {/* Show a different icon depending on whether the person is known or unknown */}
                {event.classification === "Unknown" ? (
                  <AlertCircle className="w-5 h-5 text-orange-600 mt-1 flex-shrink-0" />
                ) : (
                  <UserCheck className="w-5 h-5 text-green-600 mt-1 flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  {/* Colour-coded classification badge */}
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`text-sm px-2 py-1 rounded border ${
                        event.classification === "Unknown"
                          ? "bg-orange-100 border-orange-300 text-orange-800"
                          : "bg-green-100 border-green-300 text-green-800"
                      }`}
                    >
                      {event.classification}
                    </span>
                  </div>
                  <p className="mb-1">{event.description}</p>
                  <p className="text-sm text-gray-600">{event.timestamp}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
