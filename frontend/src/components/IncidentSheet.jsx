import { useEffect, useState } from "react";
import { CheckCircle2, Send } from "lucide-react";
import { Badge, Sheet, toast } from "../ui";
import { getJSON, postJSON } from "../lib/api";
import { HAZARD_LABEL, LEVEL_TONE, TEAMS, ago } from "../lib/labels";

const FACT_ROWS = [
  ["Hazard", (f) => HAZARD_LABEL[f.hazard]],
  ["Locality", (f) => f.locality],
  ["Landmark", (f) => f.landmark],
  ["People", (f) => f.people_count],
  ["Trapped", (f) => (f.trapped == null ? null : f.trapped ? "Yes" : "No")],
  ["On roof", (f) => (f.on_roof == null ? null : f.on_roof ? "Yes" : "No")],
  ["Water level", (f) => f.water_level],
  ["Vulnerable", (f) => f.vulnerable.join(", ")],
  ["Injuries", (f) => f.injuries.join(", ")],
  ["Medical needs", (f) => f.medical_needs.join(", ")],
  ["Needs", (f) => f.needs.join(", ")],
];

function SeverityDrivers({ drivers }) {
  return (
    <div className="sev-drivers">
      {drivers.map((d) => (
        <div className="sev-driver" key={d.label}>
          <span className="text-2">{d.label}</span>
          <span className="bar"><i style={{ width: `${Math.min(100, (d.contribution / 40) * 100)}%` }} /></span>
          <span className="val">+{d.contribution}</span>
        </div>
      ))}
    </div>
  );
}

function DispatchForm({ inc }) {
  const [team, setTeam] = useState(TEAMS[0]);
  const [note, setNote] = useState("");
  const [eta, setEta] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      await postJSON(`/api/incidents/${inc.id}/dispatch`, { team, note, eta: eta.trim() || null });
      toast(`${team} dispatched. The caller hears it in their language.`, "ok");
    } catch (e) {
      toast(`Dispatch failed: ${e.message}`, "warn");
    }
    setBusy(false);
  };
  return (
    <div className="stack" style={{ gap: 10 }}>
      <label className="field"><span>Team</span>
        <select className="select" value={team} onChange={(e) => setTeam(e.target.value)}>
          {TEAMS.map((t) => <option key={t}>{t}</option>)}
        </select>
      </label>
      <label className="field"><span>Note</span>
        <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional" />
      </label>
      <label className="field"><span>ETA (only what you can confirm)</span>
        <input className="input" value={eta} onChange={(e) => setEta(e.target.value)} placeholder="e.g. 25 min" />
      </label>
      <button className="btn primary block" onClick={send} disabled={busy}><Send size={16} /> Confirm dispatch</button>
    </div>
  );
}

export default function IncidentSheet({ inc, guidance, onClose }) {
  const [calls, setCalls] = useState([]);
  useEffect(() => {
    if (!inc) return;
    Promise.all(inc.call_ids.map((id) => getJSON(`/api/calls/${id}`).catch(() => null)))
      .then((cs) => setCalls(cs.filter(Boolean)));
  }, [inc?.id, inc?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const resolve = () => postJSON(`/api/incidents/${inc.id}/resolve`).then(onClose).catch((e) => toast(e.message, "warn"));
  const f = inc?.facts;

  return (
    <Sheet open={!!inc} onClose={onClose} title={inc ? (f.locality || f.landmark || "Unknown location") : ""}>
      {inc && (
        <div className="stack">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Badge tone={LEVEL_TONE[inc.severity.level]} dot>{inc.severity.level} · {inc.severity.score}</Badge>
            <Badge tone="muted">{inc.status}</Badge>
            <Badge tone="muted">{inc.call_ids.length} caller{inc.call_ids.length > 1 ? "s" : ""}</Badge>
            <span className="small muted">{ago(inc.updated_at)}</span>
          </div>

          <section>
            <h4>Why this severity</h4>
            <SeverityDrivers drivers={inc.severity.drivers} />
            <p className="pill-src">Fixed rule table. The LLM only extracts facts; it never decides who is rescued first.</p>
          </section>

          <section>
            <h4>Facts</h4>
            <dl className="facts">
              {FACT_ROWS.map(([k, get]) => {
                const v = get(f);
                return v || v === 0 ? [<dt key={`${k}t`}>{k}</dt>, <dd key={`${k}d`}>{v}</dd>] : null;
              })}
              <dt>Location</dt>
              <dd>{inc.lat == null ? "Unknown" : `${inc.lat.toFixed(4)}, ${inc.lon.toFixed(4)} · ${inc.loc_source} · ${Math.round(inc.loc_confidence * 100)}%`}</dd>
            </dl>
          </section>

          {inc.guidance_given.length > 0 && (
            <section>
              <h4>Approved guidance given</h4>
              {inc.guidance_given.map((id) => (
                <div key={id} className="small"><b className="mono">{id}</b> {guidance.find((g) => g.id === id)?.text_en}</div>
              ))}
            </section>
          )}

          <section>
            <h4>Dispatch</h4>
            {inc.dispatch ? (
              <div className="callout">
                <CheckCircle2 size={18} className="flex-none" />
                <span><b>{inc.dispatch.team}</b>{inc.dispatch.eta ? ` · ETA ${inc.dispatch.eta}` : ""}{inc.dispatch.note ? ` · ${inc.dispatch.note}` : ""}</span>
              </div>
            ) : <DispatchForm inc={inc} />}
            {inc.status !== "resolved" && <button className="btn ghost block" style={{ marginTop: 8 }} onClick={resolve}>Mark resolved</button>}
          </section>

          <section>
            <h4>Transcript{calls.length > 1 ? "s" : ""}</h4>
            {calls.map((c) => (
              <div key={c.id} className="captions" style={{ marginBottom: 10 }}>
                <span className="pill-src">Call {c.id} · {c.lang}</span>
                {c.turns.map((t, i) => (
                  <div key={i} className={`cap ${t.speaker}`}><b>{t.speaker === "pukaar" ? "Pukaar" : "Caller"}:</b> {t.text}</div>
                ))}
              </div>
            ))}
          </section>
        </div>
      )}
    </Sheet>
  );
}
