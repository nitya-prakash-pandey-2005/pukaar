import { useEffect, useRef, useState } from "react";
import { Headphones, MapPin, MessageSquare, PhoneCall, PhoneIncoming, PhoneMissed, PhoneOff, ShieldAlert } from "lucide-react";
import { Badge, Card, Hud, Seg, toast } from "../ui";
import { DISCLAIMER, LEVEL_TONE, jitter, mmss } from "../lib/labels";
import { useNow } from "../state/useCall";
import { postJSON } from "../lib/api";
import { DEMO, autoplayWanted, takeAutoplay } from "../demo/demo";

const NOISE_OPTIONS = [
  { value: "off", label: "Off" },
  { value: "20", label: "20 dB" },
  { value: "10", label: "10 dB" },
  { value: "5", label: "5 dB" },
  { value: "0", label: "0 dB" },
];
const STT_BADGE = {
  idle: ["muted", "Line idle"],
  connecting: ["cyan", "Connecting…"],
  connected: ["green", "Prisma listening"],
  reconnecting: ["amber", "Reconnecting…"],
  error: ["rose", "Speech service error"],
};
export const noiseToDb = (v) => (v === "off" ? null : Number(v));

export default function CallerPhone({ call, places, placeName, setPlaceName, noise, setNoise }) {
  const live = ["connecting", "live", "ending"].includes(call.phase);
  const now = useNow(live);
  const elapsed = live && call.startedAt ? (now - call.startedAt) / 1000 : call.phase === "ended" ? call.seconds : 0;
  const ringRef = useRef(null);
  const [tone, label] = STT_BADGE[call.stt] || STT_BADGE.idle;
  const level = call.incident?.severity?.level;

  // avatar ring pulses with Pukaar's voice level (DOM writes, no re-renders)
  useEffect(() => {
    if (!live) {
      if (ringRef.current) ringRef.current.style.transform = "scale(1)";
      return undefined;
    }
    let raf;
    const tick = () => {
      const lv = call.playerLevel();
      if (ringRef.current) ringRef.current.style.transform = `scale(${1 + lv * 0.18})`;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [live, call.playerLevel]);

  const gps = () => {
    const p = places.find((x) => x.name === placeName);
    return p ? jitter([p.lat, p.lon]) : null;
  };
  const startCall = () => call.start(gps(), noiseToDb(noise));
  const startRef = useRef(startCall);
  startRef.current = startCall;
  // demo build, arrived from a landing CTA: play the recorded call without hunting for the button
  useEffect(() => {
    if (!autoplayWanted()) return undefined;
    const id = setTimeout(() => { if (takeAutoplay()) startRef.current(); }, 900); // places load first
    return () => clearTimeout(id);
  }, []);
  const changeNoise = (v) => {
    setNoise(v);
    if (live) call.setNoise(noiseToDb(v));
  };

  return (
    <Card className="phone glow">
      <div className="row between">
        <Hud tone="pink">Caller phone</Hud>
        <Badge tone={tone} dot>{label}</Badge>
      </div>

      <div className="avatar-wrap">
        <div className={`ring ${live ? "live" : ""}`} ref={ringRef}>
          <div className="face brand-face"><img src="/icons/icon.svg" alt="Pukaar" width="108" height="108" /></div>
        </div>
      </div>

      <div className="who">
        <b>Pukaar helpline</b>
        <div className="small muted">Language: {call.language || "Auto"} · Tamil, Tanglish, Hindi, Telugu, English</div>
        <div className="call-timer">
          {call.phase === "idle" && "Ready"}
          {call.phase === "missed" && "Missed call sent · no balance used"}
          {call.phase === "incoming" && "Pukaar is calling you back…"}
          {call.phase === "connecting" && "Connecting…"}
          {(call.phase === "live" || call.phase === "ending") && <>{call.speaking ? "Pukaar speaking · " : "On call · "}{mmss(elapsed)}</>}
          {call.phase === "ended" && <>Call ended · {mmss(call.seconds)}</>}
        </div>
        {level && <div style={{ marginTop: 8 }}><Badge tone={LEVEL_TONE[level]} dot>Severity: {level}</Badge></div>}
      </div>

      {call.callbacks.length > 0 && (
        <div className="callout missed">
          <PhoneIncoming size={18} className="flex-none" />
          <div className="grow">
            <b>Missed callback from the control room</b>
            {call.callbacks.map((cb) => (
              <div key={cb.id} className="stack" style={{ gap: 6, marginTop: 6 }}>
                <span className="small">{cb.text}</span>
                <audio controls preload="none" src={`/api/calls/${call.callId}/callbacks/${cb.id}/audio`} />
              </div>
            ))}
          </div>
        </div>
      )}

      {call.phase === "incoming" ? (
        <div className="row" style={{ gap: 10 }}>
          <button className="btn primary lg grow ringing" onClick={() => call.answer(noiseToDb(noise))}><PhoneIncoming size={18} /> Answer</button>
          <button className="btn danger lg" onClick={call.decline} aria-label="Decline"><PhoneOff size={18} /></button>
        </div>
      ) : call.phase === "missed" ? (
        <button className="btn lg block" disabled><PhoneMissed size={18} /> Missed call sent…</button>
      ) : live ? (
        <button className="btn danger lg block" onClick={call.hangup} disabled={call.phase === "ending"}>
          <PhoneOff size={18} /> {call.phase === "ending" ? "Hanging up…" : "Hang up"}
        </button>
      ) : (
        <div className="stack" style={{ gap: 8 }}>
          <button className="btn primary lg block" onClick={startCall}>
            <PhoneCall size={18} /> {DEMO ? "Play a recorded call" : "Call Pukaar"}
          </button>
          {DEMO && <span className="pill-src">Replays a real Tamil call from the live run, with the caller's audio and Pukaar's greeting. Pukaar's replies were streamed, so they appear as captions. No microphone needed.</span>}
          <button className="btn ghost block" onClick={() => call.missedCall(gps())}>
            <PhoneMissed size={16} /> No balance? Give a missed call
          </button>
          <SmsBox gps={gps} />
        </div>
      )}

      <label className="field">
        <span><MapPin size={13} /> Simulated phone location</span>
        <select className="select" value={placeName} onChange={(e) => setPlaceName(e.target.value)} disabled={live || call.phase === "incoming"}>
          <option value="">No location shared</option>
          {places.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
        </select>
        <span className="pill-src">Sent like a phone's emergency location: the locality, jittered within 150 m</span>
      </label>

      <div className="field">
        <span>Rain and wind (SNR)</span>
        <Seg options={NOISE_OPTIONS} value={noise} onChange={changeNoise} />
        <span className="pill-src">Mixes noise into the caller's 8 kHz audio before Prisma hears it</span>
      </div>

      {call.turns.length > 0 && (
        <div className="captions">
          {call.turns.slice(-4).map((t, i) => (
            <div key={i} className={`cap ${t.speaker}`}><b>{t.speaker === "pukaar" ? "Pukaar" : "You"}:</b> {t.text}</div>
          ))}
        </div>
      )}

      <div className="callout">
        <Headphones size={18} className="flex-none" />
        <span>Use earphones, so Pukaar doesn't hear itself.</span>
      </div>

      <div className="disclaimer">
        <ShieldAlert size={15} className="flex-none" />
        <span>{DISCLAIMER}</span>
      </div>
    </Card>
  );
}

// Weak network or can't speak? Send an SMS / WhatsApp; it goes through the same triage and onto the map
function SmsBox({ gps }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      const r = await postJSON("/api/sms", { text, gps: gps() });
      setReply(r.reply);
      setText("");
    } catch (e) { toast(`SMS failed: ${e.message}`, "warn"); }
    setBusy(false);
  };
  if (!open) return <button className="btn ghost block" onClick={() => setOpen(true)}><MessageSquare size={16} /> Can't call? Send an SMS</button>;
  return (
    <div className="stack" style={{ gap: 6 }}>
      <textarea className="textarea" rows={3} value={text} onChange={(e) => setText(e.target.value)}
        placeholder="வேளச்சேரி ல மாடி மேல நாலு பேர் இருக்கோம்… / Velachery, 4 people on the roof…" />
      <button className="btn block" onClick={send} disabled={busy || !text.trim()}><MessageSquare size={16} /> {busy ? "Sending…" : "Send SMS"}</button>
      {reply && <div className="callout small"><b>Pukaar:</b> {reply}</div>}
    </div>
  );
}
