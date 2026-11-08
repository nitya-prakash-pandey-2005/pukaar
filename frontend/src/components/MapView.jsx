import { useEffect, useRef } from "react";
import L from "leaflet";
import { levelColor } from "../lib/labels";

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

export default function MapView({ incidents, selectedId, onSelect }) {
  const el = useRef(null);
  const map = useRef(null);
  const layer = useRef(null);

  useEffect(() => {
    map.current = L.map(el.current, { zoomControl: true }).setView(CENTRE, 11);
    L.tileLayer(TILES, { attribution: ATTRIBUTION, maxZoom: 19 }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    // the map may start in a hidden tab (zero size); re-measure whenever it becomes visible or resizes
    const ro = new ResizeObserver(() => map.current.invalidateSize());
    ro.observe(el.current);
    return () => { ro.disconnect(); map.current.remove(); };
  }, []);

  useEffect(() => {
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
    const inc = incidents.find((i) => i.id === selectedId);
    if (inc?.lat != null) map.current.flyTo([inc.lat, inc.lon], 14, { duration: 0.8 });
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div className="map" ref={el} />;
}
