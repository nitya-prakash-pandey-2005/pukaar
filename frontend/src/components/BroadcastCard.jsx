import { useState } from "react";
import { Megaphone } from "lucide-react";
import { Card, toast } from "../ui";
import { postJSON } from "../lib/api";

const LANGS = [["ta-IN", "Tamil"], ["hi-IN", "Hindi"], ["te-IN", "Telugu"], ["en-IN", "English"], ["ml-IN", "Malayalam"], ["kn-IN", "Kannada"], ["bn-IN", "Bengali"]];
const DEFAULT = "Flood alert: the Adyar river is rising. People in low-lying parts of Kotturpuram and Saidapet, move to the nearest relief camp now. Do not walk through flowing water.";

// District officer: one English alert, spoken by Gnani Timbre in every chosen language
export default function BroadcastCard() {
  const [text, setText] = useState(DEFAULT);
  const [langs, setLangs] = useState(["ta-IN", "hi-IN", "te-IN", "en-IN"]);
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const toggle = (l) => setLangs((ls) => (ls.includes(l) ? ls.filter((x) => x !== l) : [...ls, l]));
  const send = async () => {
    setBusy(true);
    try {
      setItems(await postJSON("/api/broadcast", { text_en: text, langs }));
    } catch (e) {
      toast(`Broadcast failed: ${e.message}`, "warn");
    }
    setBusy(false);
  };
  return (
    <Card title="Broadcast alert in every language" icon={Megaphone}>
      <div className="stack" style={{ gap: 10 }}>
        <textarea className="textarea" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
        <div className="lang-chips">
          {LANGS.map(([code, name]) => (
            <button key={code} className={`lchip ${langs.includes(code) ? "on" : ""}`} onClick={() => toggle(code)} aria-pressed={langs.includes(code)}>{name}</button>
          ))}
        </div>
        <button className="btn primary" onClick={send} disabled={busy || !text.trim() || !langs.length}>
          <Megaphone size={16} /> {busy ? "Translating and speaking…" : `Speak in ${langs.length} language${langs.length === 1 ? "" : "s"}`}
        </button>
        {items.map((i) => (
          <div key={i.lang} className="bcast">
            <b>{i.language}</b>
            <span className="small">{i.text}</span>
            <audio controls preload="none" src={i.audio_url} />
          </div>
        ))}
      </div>
    </Card>
  );
}
