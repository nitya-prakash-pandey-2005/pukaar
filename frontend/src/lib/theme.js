// Theme switching: themes are CSS variable sets in styles/tokens.css, selected with <html data-theme="...">.
export const THEMES = [
  { id: "aurora", label: "Aurora", swatch: "linear-gradient(135deg,#ff4d9d,#a855f7,#22d3ee)" },
  { id: "ocean", label: "Ocean", swatch: "linear-gradient(135deg,#38bdf8,#6366f1,#2dd4bf)" },
  { id: "ember", label: "Ember", swatch: "linear-gradient(135deg,#fb923c,#f43f5e,#facc15)" },
  { id: "forest", label: "Forest", swatch: "linear-gradient(135deg,#34d399,#84cc16,#22d3ee)" },
];
const KEY = "ui-theme";

export function getTheme() {
  try { return localStorage.getItem(KEY) || "aurora"; } catch { return "aurora"; }
}

export function setTheme(id) {
  document.documentElement.setAttribute("data-theme", id);
  try { localStorage.setItem(KEY, id); } catch { /* storage blocked */ }
}

// call once at startup (main.jsx)
export function applySavedTheme() {
  document.documentElement.setAttribute("data-theme", getTheme());
}
