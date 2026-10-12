// Route definitions — maps every URL path to its screen component
// When the user navigates to a path, react-router renders the matching Component
import { createBrowserRouter, redirect } from "react-router";
import { RequireAuth } from "./AuthContext.jsx";
import { LoginScreen } from "./screens/LoginScreen.jsx";
import { DashboardScreen } from "./screens/DashboardScreen.jsx";
import { LiveFeedScreen } from "./screens/LiveFeedScreen.jsx";
import { EventHistoryScreen } from "./screens/EventHistoryScreen.jsx";
import { EventDetailScreen } from "./screens/EventDetailScreen.jsx";
import { RegisterResidentScreen } from "./screens/RegisterResidentScreen.jsx";
import { AlertSettingsScreen } from "./screens/AlertSettingsScreen.jsx";
import { ChangePasswordScreen } from "./screens/ChangePasswordScreen.jsx";

export const router = createBrowserRouter([
  {
    path: "/",             // Entry point — the guard below sends logged-out users to /login
    loader: () => redirect("/dashboard"),
  },
  {
    path: "/login",        // Login screen — the first page a logged-out user sees
    Component: LoginScreen,
  },
  {
    // Route guard — every screen below requires a login token; without one
    // RequireAuth redirects to /login
    Component: RequireAuth,
    children: [
      {
        path: "/dashboard",    // Main hub — links to all other features
        Component: DashboardScreen,
      },
      {
        path: "/live-feed",    // Camera stream + face detection — the main feature
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
      {
        path: "/change-password", // Change the logged-in account's password
        Component: ChangePasswordScreen,
      },
    ],
  },
]);
