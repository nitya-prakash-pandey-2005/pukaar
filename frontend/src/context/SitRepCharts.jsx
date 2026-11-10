// Two small charts for the printable SitRep (white paper): the severity mix and people by hotspot locality.
// Plain HTML bars from the same report data, so they print exactly as shown and need no chart library.
const LEVELS = [["critical", "#e11d48"], ["high", "#d97706"], ["medium", "#0891b2"], ["low", "#64748b"]];

export default function SitRepCharts({ r }) {
  const total = LEVELS.reduce((n, [l]) => n + (r.by_level?.[l] || 0), 0);
  const spots = (r.hotspots || []).slice(0, 6);
  const max = Math.max(1, ...spots.map((h) => h.people || 0));
  const colour = Object.fromEntries(LEVELS);
  return (
    <section className="sr-charts">
      <div>
        <h2>Severity mix · {total} incidents</h2>
        <div className="sr-stack" role="img" aria-label={LEVELS.map(([l]) => `${l} ${r.by_level?.[l] || 0}`).join(", ")}>
          {LEVELS.map(([l, c]) => (r.by_level?.[l] ? <span key={l} style={{ flexGrow: r.by_level[l], background: c }}>{r.by_level[l]}</span> : null))}
        </div>
        <div className="sr-key">{LEVELS.map(([l, c]) => <span key={l}><i style={{ background: c }} />{l}</span>)}</div>
      </div>
      {spots.length > 0 && (
        <div>
          <h2>People by locality</h2>
          <ul className="sr-hbars">
            {spots.map((h) => (
              <li key={h.place}><span>{h.place}</span><span className="sr-hbar"><i style={{ width: `${(h.people / max) * 100}%`, background: colour[h.max_level] || "#64748b" }} /></span><b>{h.people}</b></li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
