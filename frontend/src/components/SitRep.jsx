import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Download, FileText, Printer, X } from "lucide-react";
import { toast } from "../ui";
import { getJSON } from "../lib/api";

const LEVELS = ["critical", "high", "medium", "low"];

function download(md, ts) {
  const url = URL.createObjectURL(new Blob([md], { type: "text/markdown;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `pukaar-sitrep-${new Date(ts * 1000).toISOString().slice(0, 16).replace(":", "")}.md` });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// A clean, light, printable district report (print to PDF) with a Markdown download
function Report({ r, onClose }) {
  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    document.body.classList.add("printing-sitrep");
    return () => { window.removeEventListener("keydown", esc); document.body.classList.remove("printing-sitrep"); };
  }, [onClose]);
  const cw = r.critical_waiting;
  const v = r.vulnerable;
  return createPortal(
    <div className="sitrep-overlay" role="dialog" aria-label="Situation report">
      <div className="sitrep-bar no-print">
        <button className="btn sm primary" onClick={() => window.print()}><Printer size={14} /> Print / save PDF</button>
        <button className="btn sm" onClick={() => download(r.markdown, r.generated_at)}><Download size={14} /> Download .md</button>
        <button className="btn sm ghost icon" onClick={onClose} aria-label="Close"><X size={16} /></button>
      </div>
      <article className="sitrep-paper">
        <header>
          <div className="sr-kicker">Pukaar · District situation report</div>
          <h1>{r.district} floods</h1>
          <div className="sr-sub">Generated {new Date(r.generated_at * 1000).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })} · synthetic demo data</div>
        </header>
        <section className="sr-tiles">
          <div><b>{r.calls}</b><span>calls answered</span></div>
          <div><b>{r.incidents}</b><span>incidents</span></div>
          <div><b>{r.people_affected}</b><span>people affected (open)</span></div>
          <div className="crit"><b>{cw.count}</b><span>critical waiting{cw.count ? ` · avg ${cw.avg_min} min · oldest ${cw.oldest_min} min` : ""}</span></div>
        </section>
        <section className="sr-cols">
          <div>
            <h2>By severity</h2>
            <table><tbody>{LEVELS.map((l) => <tr key={l}><td><i className={`sr-dot ${l}`} />{l}</td><td>{r.by_level[l]}</td></tr>)}</tbody></table>
            <h2>Status</h2>
            <table><tbody>
              <tr><td>Waiting for a team</td><td>{r.status.waiting}</td></tr>
              <tr><td>Dispatched</td><td>{r.status.dispatched}</td></tr>
              <tr><td>Resolved</td><td>{r.status.resolved}</td></tr>
            </tbody></table>
          </div>
          <div>
            <h2>Vulnerable households</h2>
            <table><tbody>
              <tr><td>Elderly</td><td>{v.elderly}</td></tr>
              <tr><td>Children or infants</td><td>{v.children}</td></tr>
              <tr><td>Medical needs</td><td>{v.medical}</td></tr>
              <tr><td>Disabled</td><td>{v.disabled}</td></tr>
              <tr><td>Trapped</td><td>{r.trapped}</td></tr>
              <tr><td>On a roof</td><td>{r.on_roof}</td></tr>
            </tbody></table>
          </div>
        </section>
        <section>
          <h2>Hotspots by locality</h2>
          {r.hotspots.length === 0 ? <p>None.</p> : (
            <table className="sr-wide"><thead><tr><th>Locality</th><th>Incidents</th><th>People</th><th>Worst</th></tr></thead>
              <tbody>{r.hotspots.map((h) => <tr key={h.place}><td>{h.place}</td><td>{h.incidents}</td><td>{h.people}</td><td><i className={`sr-dot ${h.max_level}`} />{h.max_level}</td></tr>)}</tbody></table>
          )}
        </section>
        <section>
          <h2>Recent timeline</h2>
          {r.timeline.length === 0 ? <p>Nothing yet.</p> : (
            <ul className="sr-timeline">{r.timeline.map((e, k) => <li key={k}><span>{e.time}</span>{e.text}</li>)}</ul>
          )}
        </section>
        <footer>Severity is a fixed rule table over the facts callers gave. Vulnerable and trapped figures count households, not people. A human confirms every dispatch.</footer>
      </article>
    </div>,
    document.body,
  );
}

export default function SitRepButton() {
  const [r, setR] = useState(null);
  const [busy, setBusy] = useState(false);
  const open = async () => {
    setBusy(true);
    try { setR(await getJSON("/api/sitrep")); } catch (e) { toast(`SitRep failed: ${e.message}`, "warn"); }
    setBusy(false);
  };
  return (
    <>
      <button className="btn sm ghost" onClick={open} disabled={busy} data-tour="sitrep" title="District situation report: print to PDF or download Markdown"><FileText size={14} /> SitRep</button>
      {r && <Report r={r} onClose={() => setR(null)} />}
    </>
  );
}
