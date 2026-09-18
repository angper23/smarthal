// Event Detail screen — shows full information about a single detection event
// The event ID comes from the URL (e.g. /event-detail/1) and is used to look up mock data
import { useNavigate, useParams } from "react-router";
import { ArrowLeft } from "lucide-react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

// Mock event details — in a real app this would be fetched from a database using the event ID
const mockEventDetails = {
  "1": {
    id: "1",
    timestamp: "March 10, 2026 at 2:45 PM",
    classification: "Unknown",
    description: "Unknown individual detected at front door",
    location: "Front Door Camera",
  },
  "2": {
    id: "2",
    timestamp: "March 10, 2026 at 10:30 AM",
    classification: "Resident",
    description: "Resident identified: John Smith",
    location: "Front Door Camera",
  },
  "3": {
    id: "3",
    timestamp: "March 9, 2026 at 6:15 PM",
    classification: "Unknown",
    description: "Unknown individual detected at front door",
    location: "Front Door Camera",
  },
};

export function EventDetailScreen() {
  const navigate = useNavigate();

  // useParams reads the :id from the URL — e.g. /event-detail/2 gives id = "2"
  const { id } = useParams();

  // Look up the event by ID — fall back to event "1" if the ID isn't found
  const event = mockEventDetails[id || "1"] || mockEventDetails["1"];

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Header with back button to event history */}
      <div className="bg-white border-b-2 border-gray-300 p-4 flex items-center gap-3">
        <button onClick={() => navigate("/event-history")} className="p-1 hover:bg-gray-100 rounded">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-2xl">Event Detail</h1>
      </div>

      <div className="p-4 space-y-4">

        {/* Snapshot image — placeholder image from Unsplash for the prototype */}
        <div className="bg-white border-2 border-gray-300 rounded-lg overflow-hidden">
          <div className="aspect-video bg-gray-200 flex items-center justify-center">
            <ImageWithFallback
              src="https://images.unsplash.com/photo-1558002038-1055907df827"
              alt="Event snapshot"
              className="w-full h-full object-cover"
            />
          </div>
          <div className="p-4 border-t-2 border-gray-300">
            <p className="text-sm text-gray-600">Snapshot Image</p>
          </div>
        </div>

        {/* Event info fields */}
        <div className="bg-white border-2 border-gray-300 rounded-lg p-4 space-y-3">

          {/* When the event happened */}
          <div>
            <label className="text-sm text-gray-600 block mb-1">Event Timestamp</label>
            <p>{event.timestamp}</p>
          </div>

          {/* Whether the person was a known resident or unknown */}
          <div className="border-t-2 border-gray-200 pt-3">
            <label className="text-sm text-gray-600 block mb-1">Classification</label>
            <span
              className={`inline-block px-3 py-1 rounded border ${
                event.classification === "Unknown"
                  ? "bg-orange-100 border-orange-300 text-orange-800"
                  : "bg-green-100 border-green-300 text-green-800"
              }`}
            >
              {event.classification}
            </span>
          </div>

          {/* Description of what happened */}
          <div className="border-t-2 border-gray-200 pt-3">
            <label className="text-sm text-gray-600 block mb-1">Description</label>
            <p>{event.description}</p>
          </div>

          {/* Which camera captured the event */}
          <div className="border-t-2 border-gray-200 pt-3">
            <label className="text-sm text-gray-600 block mb-1">Location</label>
            <p>{event.location}</p>
          </div>
        </div>

        {/* Back button */}
        <button
          onClick={() => navigate("/event-history")}
          className="w-full py-3 bg-gray-800 text-white rounded border-2 border-gray-800 hover:bg-gray-700"
        >
          Back to Event History
        </button>
      </div>
    </div>
  );
}
