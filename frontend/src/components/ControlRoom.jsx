import { useCallback, useState } from "react";
import { ListOrdered, Map as MapIcon, Waves } from "lucide-react";
import { Badge, Card, Stat, toast } from "../ui";
import { postJSON, useApi } from "../lib/api";
import { HAZARD_LABEL, LEVEL_TONE, ago } from "../lib/labels";
import MapView from "./MapView";
import IncidentSheet from "./IncidentSheet";
import DrillCard from "./DrillCard";
import BroadcastCard from "./BroadcastCard";
import PlanCard from "./PlanCard";
import HotspotsCard from "./HotspotsCard";
import SitRepButton from "./SitRep";
import SituationCard from "../context/SituationCard";
import CountUp from "../motion/CountUp";

function Kpis({ k }) {
  return (
    <div className="kpis">
      <Card><Stat value={<CountUp value={k?.calls ?? 0} />} label="Calls answered" /></Card>
      <Card><Stat value={<CountUp value={k?.avg_answer_s ?? "–"} />} unit={k?.avg_answer_s != null ? "s" : ""} label="Average reply time" /></Card>
      <Card><Stat value={<CountUp value={k?.critical_open ?? 0} />} label="Critical open" tone={k?.critical_open ? "rose" : undefined} /></Card>
      <Card><Stat value={<CountUp value={k?.people_affected ?? 0} />} label="People affected" /></Card>
    </div>
  );
}

export default function ControlRoom({ control, guidance }) {
  const [selectedId, setSelectedId] = useState(null);
  const [preset, setPreset] = useState(null); // a planned team for the incident being reviewed (fills the form only)
  const select = useCallback((id) => { setSelectedId(id); setPreset(null); }, []);
  const review = useCallback((id, p) => { setSelectedId(id); setPreset(p && { ...p, incident_id: id, n: Date.now() }); }, []);
  const { incidents, kpis, liveCalls, online } = control;
  const version = incidents.map((i) => `${i.id}:${i.status}:${i.updated_at}`).join(",");
  const hot = useApi("/api/hotspots", [version]).data;
  const selected = incidents.find((i) => i.id === selectedId) || null;
  const surge = () => postJSON("/api/surge", { n: 20 })
    .then(() => toast("Flood-night surge: 20 synthetic callers incoming", "info"))
    .catch((e) => toast(e.message.endsWith("409") ? "A surge is already running" : e.message, "warn"));

  return (
    <div className="stack">
      <Kpis k={kpis} />
      <Card title="Rescue map" icon={MapIcon} right={
        <div className="row" style={{ gap: 8 }}>
          <SitRepButton />
          <button className="btn sm ghost" onClick={surge} title="Synthetic text callers through the real triage. Uses the LLM only, no Gnani credits."><Waves size={14} /> Simulate surge</button>
          <Badge tone={online ? "green" : "rose"} dot>{online ? "Live" : "Reconnecting…"}</Badge>
        </div>}>
        <MapView incidents={incidents} selectedId={selectedId} onSelect={select} hotspots={hot?.clusters} />
        <p className="pill-src" style={{ marginTop: 8 }}>Surge callers are simulated text calls with synthetic data. Live calls use Gnani Prisma and Timbre.</p>
      </Card>
      <div className="cr-split">
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
                  {[HAZARD_LABEL[i.facts.hazard], i.facts.people_count && `${i.facts.people_count} ${i.facts.people_count === 1 ? "person" : "people"}`,
                    i.call_ids.length > 1 && `${i.call_ids.length} callers`, ago(i.updated_at)].filter(Boolean).join(" · ")}
                </div>
              </div>
              <span className="li-tags">
                {i.channel === "missed_call" && <Badge tone="cyan">missed call</Badge>}
                {i.channel === "text" && <Badge tone="muted">simulated</Badge>}
                <Badge tone={i.status === "new" ? "amber" : i.status === "dispatched" ? "green" : "muted"}>{i.status}</Badge>
              </span>
            </button>
          ))}
        </div>
      </Card>
      <SituationCard version={version} />
      </div>
      <div className="grid g2 cr-pair">
        <PlanCard onReview={review} />
        <HotspotsCard data={hot} onSelect={select} />
      </div>
      <BroadcastCard />
      <DrillCard />
      <IncidentSheet inc={selected} guidance={guidance} preset={preset} onClose={() => setSelectedId(null)} />
    </div>
  );
}
