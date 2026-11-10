import { useEffect, useRef } from "react";
import L from "leaflet";
import { levelColor } from "../lib/labels";
import { addHeat, heatPoints } from "../context/heat";

const CENTRE = [13.0827, 80.2707];
// CARTO basemaps now need an API key; OSM tiles are darkened in CSS (.map .leaflet-tile-pane)
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = "© OpenStreetMap contributors";

function pinIcon(inc, selected) {
  const n = inc.call_ids.length;
  const cls = `pin ${inc.severity.level} ${inc.status} ${selected ? "sel" : ""}`;
  return L.divIcon({
    className: "pin-wrap",
    html: `<div class="${cls}" style="--c:${levelColor(inc.severity.level)}">${n > 1 ? n : ""}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

// soft circle per area of need (screen pixels, so it reads at every zoom): size grows with people, colour = the
// worst severity there; real hotspots (2+ incidents within 500 m) are stronger and outlined
const areaRadius = (c) => (c.count >= 2 ? Math.min(60, 26 + 2.5 * c.people) : Math.min(36, 16 + 2 * c.people));

export default function MapView({ incidents, selectedId, onSelect, hotspots = [] }) {
  const el = useRef(null);
  const map = useRef(null);
  const layer = useRef(null);
  const areas = useRef(null);
  const heat = useRef(null);
  const points = useRef([]);

  useEffect(() => {
    map.current = L.map(el.current, { zoomControl: true }).setView(CENTRE, 11);
    L.tileLayer(TILES, { attribution: ATTRIBUTION, maxZoom: 19 }).addTo(map.current);
    areas.current = L.layerGroup().addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    heat.current = addHeat(map.current, () => points.current);
    // the map may start in a hidden tab (zero size); re-measure whenever it becomes visible or resizes
    const ro = new ResizeObserver(() => map.current.invalidateSize());
    ro.observe(el.current);
    return () => { ro.disconnect(); heat.current.remove(); map.current.remove(); };
  }, []);

  useEffect(() => {
    points.current = heatPoints(incidents);
    heat.current.update();
    layer.current.clearLayers();
    for (const inc of incidents) {
      if (inc.lat == null) continue;
      L.marker([inc.lat, inc.lon], { icon: pinIcon(inc, inc.id === selectedId), zIndexOffset: inc.severity.score * 10 })
        .bindTooltip(`${inc.facts.locality || inc.facts.landmark || "Unknown"} · ${inc.severity.level} ${inc.severity.score}`)
        .on("click", () => onSelect(inc.id))
        .addTo(layer.current);
    }
  }, [incidents, selectedId, onSelect]);

  useEffect(() => {
    areas.current.clearLayers();
    for (const c of hotspots) {
      const color = levelColor(c.max_level);
      const hot = c.count >= 2;
      L.circleMarker([c.lat, c.lon], { radius: areaRadius(c), color, weight: hot ? 1.5 : 0, dashArray: hot ? "4 4" : null,
        fillColor: color, fillOpacity: hot ? 0.28 : 0.14, interactive: hot })
        .bindTooltip(hot ? `Hotspot · ${c.count} incidents · ${c.people} people · worst ${c.max_level}` : "")
        .on("click", () => hot && onSelect(c.incident_ids[0]))
        .addTo(areas.current);
    }
  }, [hotspots, onSelect]);

  useEffect(() => {
    const inc = incidents.find((i) => i.id === selectedId);
    if (inc?.lat != null) map.current.flyTo([inc.lat, inc.lon], 14, { duration: 0.8 });
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div className="map" ref={el} />;
}
