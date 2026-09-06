// Entry point — starts the React app and injects it into the HTML page
// The <div id="root"> in index.html is where the entire app gets rendered
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Import global styles (Tailwind, theme colours, fonts)
import "./styles/index.css";

// Import the root App component which sets up routing
import App from "./app/App.tsx";

// Find the root div in index.html and mount the React app inside it
// StrictMode helps catch bugs during development by running extra checks
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
