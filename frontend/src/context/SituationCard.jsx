import { useEffect, useRef } from "react";
import { animate, stagger } from "animejs";
import { Activity, Clock3 } from "lucide-react";
import { Card } from "../ui";
import "./context.css";
import { useApi } from "../lib/api";

// Context column for the control room: the district picture at a glance, from the same /api/sitrep the SitRep uses
// (recorded snapshot in the static demo). Bars animate with anime.js (transform only); reduced motion shows them still.
const LEVELS = [["critical", "Critical", "var(--rose)"], ["high", "High", "var(--amber)"], ["medium", "Medium", "var(--cyan)"], ["low", "Low", "var(--muted)"]];
const reduce = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function SituationCard({ version }) {
  const { data: s } = useApi("/api/sitrep", [version]);
  const ref = useRef(null);
  const ready = !!s;
  useEffect(() => {
    if (!ready || reduce() || !ref.current) return;
    const a = animate(ref.current.querySelectorAll(".sit-bar > i"), { scaleX: [0, 1], duration: 900, delay: stagger(60), ease: "outExpo" });
    return () => a.revert();
  }, [ready]);
  if (!s) return <Card title="Situation" icon={Activity}><div className="small muted">Loading the district picture…</div></Card>;

  const total = Math.max(1, LEVELS.reduce((n, [k]) => n + (s.by_level?.[k] || 0), 0));
  const spots = (s.hotspots || []).slice(0, 5);
  const maxPeople = Math.max(1, ...spots.map((h) => h.people || 0));
  const v = s.vulnerable || {};
  return (
    <Card title="Situation" icon={Activity} right={<span className="pill-src">{s.district} district</span>} className="sit-card">
      <div ref={ref} className="sit">
        <div className="sit-row">
          <div className="sit-big"><b>{s.incidents}</b><span>incidents from {s.calls} calls</span></div>
          <div className="sit-big"><b>{s.people_affected}</b><span>people affected</span></div>
          <div className="sit-big"><b style={{ color: "var(--rose)" }}>{s.critical_waiting?.count ?? 0}</b><span>critical waiting{s.critical_waiting?.count ? ` · oldest ${s.critical_waiting.oldest_min} min` : ""}</span></div>
        </div>

        <h4>Severity mix</h4>
        <div className="sit-stack" role="img" aria-label={LEVELS.map(([k, l]) => `${l} ${s.by_level?.[k] || 0}`).join(", ")}>
          {LEVELS.map(([k, , c]) => (s.by_level?.[k] ? <span key={k} style={{ flexGrow: s.by_level[k], background: c }} /> : null))}
        </div>
        <div className="sit-legend">
          {LEVELS.map(([k, l, c]) => <span key={k}><i style={{ background: c }} />{l} <b>{s.by_level?.[k] || 0}</b></span>)}
          <span className="muted">· {Math.round(((s.by_level?.critical || 0) / total) * 100)}% critical</span>
        </div>

        {spots.length > 0 && <>
          <h4>People by locality</h4>
          <ul className="sit-bars">
            {spots.map((h) => (
              <li key={h.place}>
                <span className="sit-place">{h.place}</span>
                <span className="sit-bar"><i style={{ width: `${(h.people / maxPeople) * 100}%`, background: h.max_level === "critical" ? "var(--rose)" : h.max_level === "high" ? "var(--amber)" : "var(--cyan)" }} /></span>
                <b>{h.people}</b>
              </li>
            ))}
          </ul>
        </>}

        <h4>Who needs extra care</h4>
        <div className="sit-chips">
          <span>Medical needs <b>{v.medical ?? 0}</b></span>
          <span>Children <b>{v.children ?? 0}</b></span>
          <span>Elderly <b>{v.elderly ?? 0}</b></span>
          <span>Disabled <b>{v.disabled ?? 0}</b></span>
          <span>Trapped <b>{s.trapped ?? 0}</b></span>
          <span>On a roof <b>{s.on_roof ?? 0}</b></span>
        </div>

        {s.timeline?.length > 0 && <>
          <h4>Recent events</h4>
          <ol className="sit-time">
            {s.timeline.slice(0, 6).map((t, i) => <li key={i}><Clock3 size={12} /><span className="mono">{t.time}</span><span>{t.text}</span></li>)}
          </ol>
        </>}

        <p className="pill-src">How triage works: the LLM only extracts facts; a fixed rule table scores 0–100 (critical ≥ 70, high ≥ 45). A human confirms every dispatch.</p>
      </div>
    </Card>
  );
}
