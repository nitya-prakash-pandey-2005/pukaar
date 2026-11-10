// Incident density under the pins: Leaflet.heat (BSD-2-Clause), loaded on demand so it never delays the first paint.
// Weight = severity score / 100 (floor 0.3), open incidents only. Calm palette: blue → cyan → amber → rose.
const GRADIENT = { 0.25: "#0ea5e9", 0.45: "#22d3ee", 0.65: "#fbbf24", 0.85: "#fb7185", 1: "#f43f5e" };

export const heatPoints = (incidents) => incidents
  .filter((i) => i.lat != null && i.status !== "resolved")
  .map((i) => [i.lat, i.lon, Math.max(0.3, (i.severity?.score || 0) / 100)]);

export function addHeat(map, getPoints) {
  let layer = null;
  let dead = false;
  import("leaflet.heat")
    .then(({ HeatLayer }) => {
      if (dead) return;
      layer = new HeatLayer(getPoints(), { radius: 42, blur: 34, minOpacity: 0.18, maxZoom: 11, max: 1.6, gradient: GRADIENT }).addTo(map);
    })
    .catch(() => {}); // the map works without the density layer
  return {
    update: () => layer?.setLatLngs(getPoints()),
    remove: () => { dead = true; layer?.remove(); },
  };
}
