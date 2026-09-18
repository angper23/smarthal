// Root component — sets up the routing system for the entire app
// RouterProvider connects react-router to the route definitions in routes.js
import { RouterProvider } from "react-router";
import { router } from "./routes.js";

export default function App() {
  // Render the router — it decides which screen to show based on the URL
  return <RouterProvider router={router} />;
}
