import { Flame as Hot } from "lucide-react";
import { Badge, Card } from "../ui";
import { LEVEL_TONE } from "../lib/labels";

// Open incidents within 500 m of each other (single linkage): one boat run or one relief camp can serve them all
export default function HotspotsCard({ data, onSelect }) {
  const hot = (data?.clusters || []).filter((c) => c.count >= 2);
  return (
    <Card title="Hotspots" icon={Hot} tour="hotspots" right={<span className="small muted">within {data?.radius_m ?? 500} m</span>}>
      {hot.length === 0 && <div className="small muted">No two open incidents within {data?.radius_m ?? 500} m of each other yet.</div>}
      <div className="list">
        {hot.map((c) => (
          <button key={c.incident_ids.join()} className="li" onClick={() => onSelect(c.incident_ids[0], c)}>
            <Badge tone={LEVEL_TONE[c.max_level]} dot>{c.max_score}</Badge>
            <div className="grow">
              <div className="t">{c.places.join(" · ") || "Unnamed area"}</div>
              <div className="s">{c.count} incidents · {c.people} people · {c.waiting} waiting · spread {c.spread_m} m</div>
            </div>
            <Badge tone={LEVEL_TONE[c.max_level]}>{c.max_level}</Badge>
          </button>
        ))}
      </div>
      <p className="pill-src" style={{ marginTop: 8 }}>Soft circles on the map: size = people, colour = the worst severity in the area.</p>
    </Card>
  );
}
