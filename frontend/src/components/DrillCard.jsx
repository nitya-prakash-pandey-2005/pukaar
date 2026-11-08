import { CloudRain } from "lucide-react";
import { Card } from "../ui";
import { useApi } from "../lib/api";

const COLS = [["locality", "Locality"], ["people", "People"], ["water_level", "Water"], ["vulnerable_f1", "Vulnerable"], ["severity_level", "Severity"]];
const pct = (v) => `${Math.round(v * 100)}%`;

// Results of scripts/run_drill.py: synthetic calls in rain at 8 kHz, Prisma + triage vs the exact words
export default function DrillCard() {
  const { data } = useApi("/api/drill");
  const by = data?.summary?.by_snr;
  if (!by) return null;
  return (
    <Card title="Noise drill: rain on an 8 kHz phone line" icon={CloudRain}>
      <div className="drill-table" role="table">
        <div className="dr head" role="row"><span>Noise</span><span>Transcript errors</span>{COLS.map(([, l]) => <span key={l}>{l}</span>)}</div>
        {Object.entries(by).map(([snr, g]) => (
          <div className="dr" role="row" key={snr}>
            <b>{snr === "clean" ? "Clean" : `${snr} dB`}</b>
            <span className="mono">{g.cer == null ? "n/a" : `${(g.cer * 100).toFixed(1)}%`}</span>
            {COLS.map(([k]) => (
              <span key={k} className="cellbar"><i style={{ width: pct(g[k]) }} /><em>{pct(g[k])}</em></span>
            ))}
          </div>
        ))}
      </div>
      <p className="pill-src" style={{ marginTop: 8 }}>
        {by.clean?.n ?? 0} synthetic calls per row, spoken by Gnani Timbre in Tamil, Hindi, Telugu and English, heard by Gnani Prisma.
        Facts recovered from noisy audio vs from the exact words. 0 dB = rain as loud as the voice.
      </p>
    </Card>
  );
}
