// Root component — sets up the routing system for the entire app
// RouterProvider connects react-router to the route definitions in routes.js
import { RouterProvider } from "react-router";
import { router } from "./routes.js";
import { AuthProvider } from "./AuthContext.jsx";

/** Root component: gives every screen access to login state, then renders the screen for the current URL. */
export default function App() {
  // Render the router — it decides which screen to show based on the URL
  // AuthProvider sits outside it so every screen (and the route guard) can
  // read the login state
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
