export const DISCLAIMER = "Simulated emergency call: synthetic data";

export const LEVEL_TONE = { critical: "rose", high: "amber", medium: "cyan", low: "muted" };
// Leaflet needs real colour values, so read the theme tokens at draw time
export const levelColor = (level) =>
  getComputedStyle(document.documentElement).getPropertyValue(`--${LEVEL_TONE[level] || "muted"}`).trim() || "#999";

export const TEAMS = ["NDRF Boat 1", "NDRF Boat 2", "NDRF Boat 3", "NDRF Boat 4", "Fire & Rescue", "Ambulance 108", "Volunteer boat"];

export const HAZARD_LABEL = {
  flood: "Flood", cyclone: "Cyclone", landslide: "Landslide", fire: "Fire",
  building_collapse: "Building collapse", medical: "Medical", other: "Other",
};

export const mmss = (sec) => {
  const s = Math.max(0, Math.round(sec || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

export const ago = (ts) => {
  const s = Math.max(0, Date.now() / 1000 - ts);
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : `${Math.floor(s / 3600)} h ago`;
};

// a phone's emergency location: the locality centre, jittered within ~150 m
export function jitter([lat, lon], metres = 150) {
  const r = (metres * Math.sqrt(Math.random())) / 111_000;
  const a = Math.random() * 2 * Math.PI;
  return [lat + r * Math.cos(a), lon + (r * Math.sin(a)) / Math.cos((lat * Math.PI) / 180)];
}
