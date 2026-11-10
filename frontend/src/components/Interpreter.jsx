// Rescuer <-> caller interpreter (protocol: /ws/interpret in backend/pukaar/app.py, docs/API.md).
// Two push-to-talk buttons share one device (or the phone is passed between the rescuer and the caller).
// Half-duplex: the server holds a speaking lock; pressing while the other side's translation plays is a barge-in.
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Languages, Mic, Play, Square } from "lucide-react";
import { startMic } from "@voice/index.js";
import { wsUrl } from "../net/callSocket";
import { Badge, Card, toast } from "../ui";
import { DEMO } from "../demo/demo";

const RATE = 16000;
const NAMES = { "hi-IN": "Hindi", "en-IN": "English", "ta-IN": "Tamil", "te-IN": "Telugu" };
const CHOICES = { rescuer: ["hi-IN", "en-IN"], caller: ["ta-IN", "te-IN", "hi-IN", "en-IN"] };
const LABEL = { rescuer: "Rescuer", caller: "Caller" };
const sec = (ms) => (ms == null ? "–" : `${(ms / 1000).toFixed(1)} s`);

function Side({ role, lang, setLang, floor, holding, busy, onDown, onUp, disabled }) {
  const live = holding === role;
  const waiting = floor && floor !== role;
  return (
    <div className={`interp-side ${live ? "on" : ""}`}>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
        <b>{LABEL[role]}</b>
        <select className="select" aria-label={`${LABEL[role]} language`} value={lang} disabled={disabled || !!holding}
          onChange={(e) => setLang(role, e.target.value)}>
          {CHOICES[role].map((c) => <option key={c} value={c}>{NAMES[c]}</option>)}
        </select>
      </div>
      <button className={`ptt ${live ? "on" : ""}`} disabled={disabled || waiting || busy}
        onPointerDown={(e) => { e.preventDefault(); onDown(role); }} onPointerUp={() => onUp(role)}
        onPointerLeave={() => live && onUp(role)} onContextMenu={(e) => e.preventDefault()}>
        {live ? <Square size={26} /> : <Mic size={26} />}
        <span>{live ? "Release to interpret" : waiting ? `${LABEL[floor]} is speaking…` : `Hold to talk (${NAMES[lang]})`}</span>
      </button>
    </div>
  );
}

function Row({ t }) {
  const cell = (role) => {
    if (t.role === role) {
      return <div className="interp-cell said"><span className="tag">said · {NAMES[t.src_lang]}</span><p>{t.original}</p></div>;
    }
    return (
      <div className={`interp-cell heard ${t.translated ? "" : "withheld"}`}>
        <span className="tag">heard · {NAMES[t.spoken_lang]} · {t.voice}</span>
        <p>{t.translation}</p>
        {t.note && <p className="note"><AlertTriangle size={13} /> {t.note}</p>}
      </div>
    );
  };
  return (
    <div className="interp-row">
      {cell("rescuer")}
      {cell("caller")}
      <div className="interp-lat pill-src">
        Prisma {sec(t.prisma_ms)} · translation {sec(t.translate_ms)} · Timbre {sec(t.tts_ms)} · turn {sec(t.total_ms)}
      </div>
    </div>
  );
}

export default function Interpreter({ route }) {
  const preset = CHOICES.caller.includes(route?.query?.caller) ? route.query.caller : "ta-IN";
  const [langs, setLangs] = useState({ rescuer: "hi-IN", caller: preset });
  const [turns, setTurns] = useState([]);
  const [floor, setFloor] = useState(null); // role holding the speaking lock (server's view)
  const [holding, setHolding] = useState(null); // role whose mic is open here
  const [busy, setBusy] = useState(false); // a turn is being interpreted
  const [conn, setConn] = useState(DEMO ? "demo" : "connecting");
  const [replaying, setReplaying] = useState(false);
  const r = useRef({ ws: null, mic: null, audio: null, held: null, replay: null });

  const play = (url) => {
    try { r.current.audio?.pause(); } catch { /* none */ }
    const a = new Audio(url);
    r.current.audio = a;
    a.play().catch(() => { /* autoplay blocked: captions still show */ });
    return a;
  };
  const stopMic = () => { try { r.current.mic?.stop(); } catch { /* stopped */ } r.current.mic = null; };

  const onMsg = useCallback(async (m) => {
    if (m.type === "ready" || m.type === "langs") { setLangs(m.langs); setConn("live"); }
    else if (m.type === "floor") {
      if (m.stop_audio_of) { try { r.current.audio?.pause(); } catch { /* none */ } } // barge-in
      setFloor(m.role);
      if (r.current.held !== m.role) { r.current.ws?.send(JSON.stringify({ type: "cancel", role: m.role })); return; }
      try {
        r.current.mic = await startMic({ targetRate: RATE, onFrame: (ab) => r.current.ws?.readyState === 1 && r.current.ws.send(ab) });
        if (r.current.held !== m.role) { // released while the mic was starting: give the floor back
          stopMic();
          r.current.ws?.send(JSON.stringify({ type: "cancel", role: m.role }));
        }
        else setHolding(m.role);
      } catch (e) {
        toast(`Microphone unavailable: ${e?.message || e}`, "warn");
        r.current.ws?.send(JSON.stringify({ type: "cancel", role: m.role }));
      }
    } else if (m.type === "busy") {
      r.current.held = null;
      toast(`${LABEL[m.speaking] || "The other side"} is speaking. Wait for the translation.`, "info");
    } else if (m.type === "interpreting") setBusy(true);
    else if (m.type === "turn") { setTurns((ts) => [m, ...ts]); play(m.audio_url); }
    else if (m.type === "unheard") toast("Nothing was heard. Hold the button while speaking.", "info");
    else if (m.type === "floor_free") { setBusy(false); setFloor(null); }
    else if (m.type === "error") { setBusy(false); toast(m.error, "warn"); }
  }, []);

  useEffect(() => {
    if (DEMO) return undefined;
    const ws = new WebSocket(wsUrl("/ws/interpret"));
    r.current.ws = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: "start", rescuer_lang: "hi-IN", caller_lang: preset, sample_rate: RATE }));
    ws.onmessage = (e) => { try { onMsg(JSON.parse(e.data)); } catch { /* ignore */ } };
    ws.onclose = () => setConn("offline");
    return () => { stopMic(); try { r.current.audio?.pause(); ws.close(); } catch { /* closed */ } };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setLang = (role, lang) => {
    setLangs((l) => ({ ...l, [role]: lang }));
    r.current.ws?.readyState === 1 && r.current.ws.send(JSON.stringify({ type: "set_lang", role, lang }));
  };
  const down = (role) => {
    if (r.current.held) return;
    r.current.held = role;
    r.current.ws?.send(JSON.stringify({ type: "talk", role }));
  };
  const up = (role) => {
    if (r.current.held !== role) return;
    r.current.held = null;
    const had = !!r.current.mic;
    stopMic();
    setHolding(null);
    if (had) r.current.ws?.send(JSON.stringify({ type: "done", role }));
  };

  // recorded live exchange (frontend/demo/interpret/, made by scripts/interpret_live_check.py): real audio + captions
  const replay = async () => {
    if (replaying) return;
    let tl;
    try { tl = await (await fetch("/demo/interpret/timeline.json")).json(); } catch { toast("No recorded interpretation in this build.", "warn"); return; }
    setReplaying(true);
    setTurns([]);
    for (const t of tl.turns) {
      setLangs((l) => ({ ...l, [t.role]: t.src_lang }));
      setFloor(t.role);
      await new Promise((ok) => { const a = play(t.input_audio); a.onended = ok; a.onerror = ok; setTimeout(ok, (t.input_s + 1) * 1000); });
      setBusy(true);
      await new Promise((ok) => setTimeout(ok, Math.min(t.total_ms || 1500, 6000)));
      setBusy(false);
      setFloor(null);
      setTurns((ts) => [t, ...ts]);
      await new Promise((ok) => { const a = play(t.audio_url); a.onended = ok; a.onerror = ok; setTimeout(ok, (t.audio_s + 1) * 1000); });
    }
    setReplaying(false);
  };

  return (
    <div className="stack">
      <Card title="Rescuer interpreter" icon={Languages}
        right={<div className="row" style={{ marginLeft: "auto", gap: 6, flexWrap: "wrap" }}>
          <Badge tone="amber" dot>Machine interpretation</Badge>
          {conn === "live" && <Badge tone="green" dot>Connected</Badge>}
          {conn === "offline" && <Badge tone="rose" dot>Server offline</Badge>}
        </div>}>
        <p className="small muted" style={{ marginTop: 0 }}>
          For rescue teams from another state who do not speak the caller's language. The rescuer speaks Hindi or English;
          the caller hears it in Tamil, Telugu, Hindi or English in a Gnani Timbre voice, and the answer comes back translated.
          One side talks at a time. Names, places and numbers are kept; a translation that adds a time, a number or a
          "you are safe" the speaker did not say is withheld and the speaker's own words are played instead.
        </p>
        {DEMO && (
          <p className="small" style={{ marginTop: 0 }}>
            Live push-to-talk needs the Pukaar server. Here you can replay an exchange recorded on Gnani's live servers (synthetic voices).
          </p>
        )}
        <div className="interp-sides">
          {["rescuer", "caller"].map((role) => (
            <Side key={role} role={role} lang={langs[role]} setLang={setLang} floor={floor} holding={holding} busy={busy}
              onDown={down} onUp={up} disabled={DEMO || conn !== "live" || replaying} />
          ))}
        </div>
        <div className="row" style={{ marginTop: 12, flexWrap: "wrap" }}>
          {DEMO && (
            <button className="btn ghost" onClick={replay} disabled={replaying || !!holding || busy}>
              <Play size={16} /> {replaying ? "Playing the recorded interpretation…" : "Play a recorded interpretation"}
            </button>
          )}
          {busy && <span className="small muted">Interpreting…</span>}
        </div>
      </Card>

      <Card title="Live captions" right={<span className="pill-src" style={{ marginLeft: "auto" }}>newest first</span>}>
        <div className="interp-head"><b>Rescuer</b><b>Caller</b></div>
        {turns.length === 0 && <p className="small muted">No turns yet.</p>}
        <div className="interp-log" aria-live="polite">
          {turns.map((t) => <Row key={`${t.id}-${t.role}`} t={t} />)}
        </div>
      </Card>
    </div>
  );
}
