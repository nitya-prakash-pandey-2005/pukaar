import { useState } from "react";
import { Route } from "lucide-react";
import { Badge, Card, toast } from "../ui";
import { getJSON } from "../lib/api";
import { LEVEL_TONE } from "../lib/labels";

// "Plan all": one suggested team per waiting incident (most severe first, no team twice). Review opens the incident
// with the form filled; nothing is dispatched from here.
export default function PlanCard({ onReview }) {
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setPlan(await getJSON("/api/plan")); } catch (e) { toast(`Plan failed: ${e.message}`, "warn"); }
    setBusy(false);
  };
  return (
    <Card title="Dispatch plan" icon={Route} tour="plan" right={
      <button className="btn sm primary" onClick={run} disabled={busy}>{busy ? "Planning…" : plan ? "Re-plan" : "Plan all"}</button>}>
      {!plan && <div className="small muted">Suggests a free team for every waiting incident: most severe first, then the longest waiting, never the same team twice. You review and confirm each one.</div>}
      {plan && (
        <div className="stack" style={{ gap: 10 }}>
          <div className="small muted">
            {plan.assignments.length} suggested · {plan.unassigned.length} left for a human decision · {plan.teams_free.length} team{plan.teams_free.length === 1 ? "" : "s"} still free
          </div>
          <div className="list plan-list">
            {plan.assignments.map((a) => (
              <button key={a.incident_id} className="li" onClick={() => onReview(a.incident_id, { team: a.team, eta: a.eta })}>
                <Badge tone={LEVEL_TONE[a.level]} dot>{a.score}</Badge>
                <div className="grow">
                  <div className="t">{a.place} → {a.team}</div>
                  <div className="s">{a.summary}</div>
                </div>
                <span className="btn sm ghost">Review</span>
              </button>
            ))}
            {plan.unassigned.map((u) => (
              <button key={u.incident_id} className="li" onClick={() => onReview(u.incident_id, null)}>
                <Badge tone={LEVEL_TONE[u.level]} dot>{u.score}</Badge>
                <div className="grow">
                  <div className="t">{u.place}</div>
                  <div className="s">Not assigned: {u.reason}</div>
                </div>
                <Badge tone="amber">needs you</Badge>
              </button>
            ))}
          </div>
          {plan.assignments.length + plan.unassigned.length === 0 && <div className="small muted">No incident is waiting for a team.</div>}
        </div>
      )}
    </Card>
  );
}
