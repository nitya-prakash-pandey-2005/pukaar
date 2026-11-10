import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "@fontsource-variable/space-grotesk";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-tamil/400.css";
import "@fontsource/noto-sans-bengali/400.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";
import "./styles/layout.css";
import "./styles/tour.css";
import "leaflet/dist/leaflet.css";
import "./app.css";
import { applySavedTheme } from "./lib/theme";
import { DEMO, installDemo } from "./demo/demo";
import Root from "./landing/Root";

applySavedTheme();
if (DEMO) installDemo(); // static Vercel build: recorded data, no backend, no service worker
else if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
createRoot(document.getElementById("root")).render(<StrictMode><Root /></StrictMode>);
