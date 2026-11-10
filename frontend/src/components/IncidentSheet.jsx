import { useEffect, useState } from "react";
import { CheckCircle2, Languages, Send } from "lucide-react";
import { Badge, Sheet, toast } from "../ui";
import { getJSON, postJSON, useApi } from "../lib/api";
import { HAZARD_LABEL, LEVEL_TONE, TEAMS, ago } from "../lib/labels";
import { DEMO } from "../demo/demo";
import RecommendedTeams from "./RecommendedTeams";

const LOC_SOURCE = { gps: "phone location", landmark: "spoken landmark", both: "phone location + landmark" };

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

// Dispatcher types English; each caller hears it in their own language (live, or as a callback)
function MessageForm({ inc }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      const r = await postJSON(`/api/incidents/${inc.id}/message`, { text });
      toast(`Sent to ${r.sent.length} caller${r.sent.length > 1 ? "s" : ""} in ${[...new Set(r.sent.map((s) => s.lang))].join(", ")}`, "ok");
      setText("");
    } catch (e) { toast(e.message, "warn"); }
    setBusy(false);
  };
  return (
    <div className="stack" style={{ gap: 8 }}>
      <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. The boat is at the temple gate. Wave a cloth." />
      <button className="btn block" onClick={send} disabled={busy || !text.trim()}><Send size={16} /> {busy ? "Translating…" : "Send in their language"}</button>
    </div>
  );
}

// preset = a recommended team ({team, eta, n}): it only fills the form; the dispatcher still confirms
function DispatchForm({ inc, preset }) {
  const roster = useApi("/api/teams").data;
  const names = [...new Set([preset?.team, ...(roster ? roster.map((t) => t.name) : TEAMS)].filter(Boolean))];
  const busyTeams = new Set((roster || []).filter((t) => t.status !== "available").map((t) => t.name));
  const [team, setTeam] = useState(preset?.team || TEAMS[0]);
  const [note, setNote] = useState("");
  const [eta, setEta] = useState(preset?.eta || "");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (preset) { setTeam(preset.team); setEta(preset.eta || ""); }
  }, [preset?.n]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { // first roster load: start on a free roster team, not the fallback list
    if (roster?.length && !preset && !roster.some((t) => t.name === team && t.status === "available")) {
      setTeam(roster.find((t) => t.status === "available")?.name || roster[0].name);
    }
  }, [roster]); // eslint-disable-line react-hooks/exhaustive-deps
  const send = async () => {
    setBusy(true);
    try {
      await postJSON(`/api/incidents/${inc.id}/dispatch`, { team, note, eta: eta.trim() || null });
      toast(`${team} dispatched. ${DEMO ? "In the live app, the caller now hears it in their language." : "The caller hears it in their language."}`, "ok");
    } catch (e) {
      toast(`Dispatch failed: ${e.message}`, "warn");
    }
    setBusy(false);
  };
  return (
    <div className="stack" style={{ gap: 10 }}>
      <label className="field"><span>Team</span>
        <select className="select" value={team} onChange={(e) => setTeam(e.target.value)}>
          {names.map((t) => <option key={t} value={t}>{busyTeams.has(t) ? `${t} (busy)` : t}</option>)}
        </select>
      </label>
      <label className="field"><span>Note</span>
        <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional" />
      </label>
      {preset && <p className="pill-src">Filled from the recommendation: check the team and ETA, then confirm.</p>}
      <label className="field"><span>ETA (only what you can confirm)</span>
        <input className="input" value={eta} onChange={(e) => setEta(e.target.value)} placeholder="e.g. 25 min" />
      </label>
      <button className="btn primary block" onClick={send} disabled={busy}><Send size={16} /> Confirm dispatch</button>
    </div>
  );
}

export default function IncidentSheet({ inc, guidance, onClose, preset: planned }) {
  const [calls, setCalls] = useState([]);
  const [preset, setPreset] = useState(null);
  useEffect(() => setPreset(planned && planned.incident_id === inc?.id ? planned : null), [inc?.id, planned?.n]); // eslint-disable-line react-hooks/exhaustive-deps
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
              <dd>{inc.lat == null ? "Unknown" : `${inc.lat.toFixed(4)}, ${inc.lon.toFixed(4)} · ${LOC_SOURCE[inc.loc_source] || inc.loc_source} · ${Math.round(inc.loc_confidence * 100)}% sure`}</dd>
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
            ) : (
              <div className="stack" style={{ gap: 12 }}>
                {inc.status === "new" && <RecommendedTeams inc={inc} onPick={(r) => setPreset({ team: r.team, eta: r.eta, n: Date.now() })} />}
                <DispatchForm key={inc.id} inc={inc} preset={preset} />
              </div>
            )}
            {inc.status !== "resolved" && <button className="btn ghost block" style={{ marginTop: 8 }} onClick={resolve}>Mark resolved</button>}
          </section>

          {inc.status !== "resolved" && (
            <section>
              <h4>Message the caller{inc.call_ids.length > 1 ? "s" : ""}</h4>
              <MessageForm inc={inc} />
              {/* rescue team from another state: live machine interpretation, caller's language preselected */}
              <a className="btn ghost block" style={{ marginTop: 8 }} href={`#/interpret?caller=${calls[0]?.lang || "ta-IN"}`}>
                <Languages size={16} /> Talk to the caller through the interpreter
              </a>
            </section>
          )}

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
