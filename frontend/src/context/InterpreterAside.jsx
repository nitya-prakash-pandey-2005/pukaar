import { useEffect, useState } from "react";
import { Gauge, Route, ShieldCheck } from "lucide-react";
import { Card } from "../ui";
import "./context.css";
import { DEMO } from "../demo/demo";

// Context column for the rescuer interpreter (wide screens): how one turn works, the guard, and in the static demo the
// step timings of the recorded exchange (demo/interpret/timeline.json, real numbers from the 10 Nov live run).
const STEPS = [
  ["Prisma v3.0", "the speaker's clip, one locale (hi-IN, en-IN, ta-IN or te-IN)"],
  ["One LLM call", "translates into the listener's language"],
  ["Guard", "no added time, number or \"you are safe\"; no dropped number"],
  ["Timbre v3.0", "speaks it: the caller hears Chetana, the rescuer Prakash"],
];
const LANG = { "hi-IN": "Hindi", "ta-IN": "Tamil", "te-IN": "Telugu", "en-IN": "English" };

export default function InterpreterAside() {
  const [turns, setTurns] = useState(null);
  useEffect(() => {
    if (!DEMO) return;
    let alive = true;
    fetch("/demo/interpret/timeline.json").then((r) => (r.ok ? r.json() : null)).then((j) => { if (alive && j) setTurns(j.turns || []); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  const timed = (turns || []).filter((t) => t.type === "turn" && t.total_ms);
  const max = Math.max(1, ...timed.map((t) => t.total_ms));

  return (
    <aside className="ctx-col">
      <Card title="One turn, four steps" icon={Route}>
        <ol className="ctx-steps">
          {STEPS.map(([t, s], i) => <li key={t}><span className="n">{i + 1}</span><div><b>{t}</b><span>{s}</span></div></li>)}
        </ol>
      </Card>
      {timed.length > 0 && (
        <Card title="Recorded exchange, step by step" icon={Gauge} right={<span className="pill-src">10 Nov · live servers</span>}>
          <div className="ctx-timing">
            {timed.map((t) => (
              <div key={t.id} className="ctx-turn">
                <div className="ctx-turn-h"><b>{LANG[t.src_lang] || t.src_lang} → {LANG[t.dst_lang] || t.dst_lang}</b><span className="mono">{(t.total_ms / 1000).toFixed(1)} s</span></div>
                <div className="ctx-seg" style={{ width: `${(t.total_ms / max) * 100}%` }}>
                  {[["stt", t.stt_ms, "var(--cyan)"], ["translate", t.translate_ms, "var(--violet-2)"], ["tts", t.tts_ms, "var(--amber)"]].map(([k, ms, c]) =>
                    ms ? <i key={k} title={`${k} ${ms} ms`} style={{ flexGrow: ms, background: c }} /> : null)}
                </div>
                <div className="ctx-seg-l mono">speech-to-text {t.stt_ms} ms · translate {t.translate_ms} ms · voice {t.tts_ms} ms</div>
              </div>
            ))}
            <p className="pill-src">Release of the button to translated audio. Timbre rendering the whole clip is the largest part.</p>
          </div>
        </Card>
      )}
      <Card title="Checked like everything Pukaar says" icon={ShieldCheck}>
        <p className="small muted" style={{ margin: 0, lineHeight: 1.55 }}>
          If a translation adds a promise or a number, or drops one, the listener hears the speaker's own words instead and both captions say why.
          One side talks at a time; pressing while the other side is still playing stops it. Labelled machine interpretation.
        </p>
      </Card>
    </aside>
  );
}
