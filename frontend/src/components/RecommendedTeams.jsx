import { Anchor, Ambulance, Flame, Stethoscope, Truck } from "lucide-react";
import { Badge } from "../ui";
import { useApi } from "../lib/api";

export const TEAM_ICON = { boat: Anchor, fire: Flame, ambulance: Ambulance, medical: Stethoscope };

// Top 3 free teams for this incident, with the reasons. One click fills the dispatch form; a human confirms.
export default function RecommendedTeams({ inc, onPick }) {
  const { data, error, loading } = useApi(`/api/incidents/${inc.id}/recommend`, [inc.updated_at]);
  const recs = data?.recommendations || [];
  return (
    <div className="rec" data-tour="recommend">
      <div className="row between" style={{ marginBottom: 6 }}>
        <b className="rec-title">Recommended teams</b>
        {data && <span className="small muted">{data.teams_free} free</span>}
      </div>
      {loading && !data && <div className="small muted">Ranking free teams…</div>}
      {error && <div className="small muted">No recommendation for this incident yet. Pick a team below.</div>}
      {data && recs.length === 0 && <div className="small muted">No suitable team is free. Pick one below or wait for a team to return.</div>}
      {recs.map((r, k) => {
        const Icon = TEAM_ICON[r.type] || Truck;
        return (
          <div key={r.team_id} className={`rec-row ${k === 0 ? "best" : ""}`}>
            <span className="ic"><Icon size={16} /></span>
            <div className="grow" style={{ minWidth: 0 }}>
              <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                <b>{r.team}</b>
                {k === 0 && <Badge tone="green">best fit</Badge>}
                <span className="mono small muted">{r.score}/100</span>
              </div>
              <div className="small text-2 rec-why">{r.summary}</div>
            </div>
            <button className="btn sm" onClick={() => onPick(r)} title="Fills the dispatch form below. You still confirm.">Dispatch this team</button>
          </div>
        );
      })}
      <p className="pill-src" style={{ marginTop: 6 }}>
        Ranked by need match, capacity and ETA from the team's base (straight line × 1.3 + 5 min to leave). Suggestions only: a person confirms every dispatch.
      </p>
    </div>
  );
}
