import { useEffect } from "react";

// App-wide motion is pure CSS (src/landing.css, "app motion" section), scoped under html.app-motion so it never touches
// the landing page and switches off for prefers-reduced-motion. Only transform and opacity are animated, and nothing
// waits for an animation before it can be clicked.
export function useAppMotion() {
  useEffect(() => {
    const html = document.documentElement;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!reduce) html.classList.add("app-motion");
    return () => html.classList.remove("app-motion");
  }, []);
}
