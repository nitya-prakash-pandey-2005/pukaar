import { useCallback, useState } from "react";
import { ListOrdered, Map as MapIcon } from "lucide-react";
import { Badge, Card, Stat } from "../ui";
import { HAZARD_LABEL, LEVEL_TONE, ago } from "../lib/labels";
import MapView from "./MapView";
import IncidentSheet from "./IncidentSheet";

function Kpis({ k }) {
  return (
    <div className="kpis">
      <Card><Stat value={k?.calls ?? 0} label="Calls answered" /></Card>
      <Card><Stat value={k?.avg_answer_s ?? "–"} unit={k?.avg_answer_s != null ? "s" : ""} label="Average reply time" /></Card>
      <Card><Stat value={k?.critical_open ?? 0} label="Critical open" tone={k?.critical_open ? "rose" : undefined} /></Card>
      <Card><Stat value={k?.people_affected ?? 0} label="People affected" /></Card>
    </div>
  );
}

export default function ControlRoom({ control, guidance }) {
  const [selectedId, setSelectedId] = useState(null);
  const select = useCallback((id) => setSelectedId(id), []);
  const { incidents, kpis, liveCalls, online } = control;
  const selected = incidents.find((i) => i.id === selectedId) || null;

  return (
    <div className="stack">
      <Kpis k={kpis} />
      <Card title="Rescue map" icon={MapIcon} right={<Badge tone={online ? "green" : "rose"} dot>{online ? "Live" : "Reconnecting…"}</Badge>}>
        <MapView incidents={incidents} selectedId={selectedId} onSelect={select} />
      </Card>
      <Card title="Queue by severity" icon={ListOrdered} right={<span className="small muted">{liveCalls.length} live call{liveCalls.length === 1 ? "" : "s"}</span>}>
        {incidents.length === 0 && <div className="small muted">No calls yet. Start a call on the caller phone.</div>}
        <div className="list">
          {incidents.map((i) => (
            <button key={i.id} className={`li ${i.status}`} onClick={() => select(i.id)}>
              <Badge tone={LEVEL_TONE[i.severity.level]} dot>{i.severity.score}</Badge>
              <div className="grow">
                <div className="t">
                  {i.facts.locality || i.facts.landmark || "Unknown location"}
                  {i.call_ids.some((c) => liveCalls.includes(c)) && <span className="live-dot" title="On a live call" />}
                </div>
                <div className="s">
                  {[HAZARD_LABEL[i.facts.hazard], i.facts.people_count && `${i.facts.people_count} people`,
                    i.call_ids.length > 1 && `${i.call_ids.length} callers`, ago(i.updated_at)].filter(Boolean).join(" · ")}
                </div>
              </div>
              <Badge tone={i.status === "new" ? "amber" : i.status === "dispatched" ? "green" : "muted"}>{i.status}</Badge>
            </button>
          ))}
        </div>
      </Card>
      <IncidentSheet inc={selected} guidance={guidance} onClose={() => setSelectedId(null)} />
    </div>
  );
}
