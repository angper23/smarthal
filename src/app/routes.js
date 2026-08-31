// Route definitions — maps every URL path to its screen component
// When the user navigates to a path, react-router renders the matching Component
import { createBrowserRouter } from "react-router";
import { LoginScreen } from "./screens/LoginScreen.jsx";
import { DashboardScreen } from "./screens/DashboardScreen.jsx";
import { LiveFeedScreen } from "./screens/LiveFeedScreen.jsx";
import { EventHistoryScreen } from "./screens/EventHistoryScreen.jsx";
import { EventDetailScreen } from "./screens/EventDetailScreen.jsx";
import { RegisterResidentScreen } from "./screens/RegisterResidentScreen.jsx";
import { AlertSettingsScreen } from "./screens/AlertSettingsScreen.jsx";

export const router = createBrowserRouter([
  {
    path: "/",             // Login screen — the first page the user sees
    Component: LoginScreen,
  },
  {
    path: "/dashboard",    // Main hub — links to all other features
    Component: DashboardScreen,
  },
  {
    path: "/live-feed",    // Webcam + face detection — the main feature
    Component: LiveFeedScreen,
  },
  {
    path: "/event-history", // List of all past detection events
    Component: EventHistoryScreen,
  },
  {
    path: "/event-detail/:id", // Detail view for a single event — :id is dynamic
    Component: EventDetailScreen,
  },
  {
    path: "/register-resident", // Form to add a new resident (mock)
    Component: RegisterResidentScreen,
  },
  {
    path: "/alert-settings", // Toggle notification preferences (mock)
    Component: AlertSettingsScreen,
  },
]);
