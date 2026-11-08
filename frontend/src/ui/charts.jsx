import { useId, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { AnimatedNumber } from "./index";

// ---------- readiness gauge (HUD ring) ----------
export function Gauge({ score = 0, label, sub, color = "var(--cyan)", size = 230, tour }) {
  const id = useId().replace(/:/g, "");
  const r = 86, c = 2 * Math.PI * r, arc = 0.78;
  const ticks = Array.from({ length: 64 }, (_, i) => i);
  return (
    <div className="gauge" data-tour={tour} style={{ width: size, height: size, position: "relative", margin: "0 auto" }}>
      <svg viewBox="0 0 220 220" width={size} height={size}>
        <defs>
          <linearGradient id={`g${id}`} x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" style={{ stopColor: "var(--pink)" }} /><stop offset="0.55" style={{ stopColor: "var(--violet)" }} /><stop offset="1" style={{ stopColor: color }} />
          </linearGradient>
          <filter id={`f${id}`} x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        {ticks.map((i) => {
          const a = (-90 - 140 + (i / 63) * 280) * (Math.PI / 180);
          const long = i % 8 === 0;
          const r1 = 104, r2 = long ? 96 : 99;
          const on = i / 63 <= score / 100;
          return <line key={i} x1={110 + r1 * Math.cos(a)} y1={110 + r1 * Math.sin(a)} x2={110 + r2 * Math.cos(a)} y2={110 + r2 * Math.sin(a)} stroke={on ? color : "rgba(255,255,255,0.12)"} strokeWidth={long ? 2 : 1.2} strokeLinecap="round" opacity={on ? 0.9 : 1} />;
        })}
        <circle cx="110" cy="110" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="12" strokeDasharray={`${c * arc} ${c}`} strokeLinecap="round" transform="rotate(130 110 110)" />
        <motion.circle cx="110" cy="110" r={r} fill="none" stroke={`url(#g${id})`} strokeWidth="12" strokeLinecap="round" transform="rotate(130 110 110)" filter={`url(#f${id})`}
          initial={{ strokeDasharray: `0 ${c}` }} animate={{ strokeDasharray: `${(c * arc * score) / 100} ${c}` }} transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }} />
        <circle cx="110" cy="110" r="66" fill="rgba(5,6,15,0.6)" stroke="rgba(255,255,255,0.05)" />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center" }}>
        <div>
          <div className="num" style={{ fontSize: size * 0.22, fontWeight: 600, lineHeight: 1 }}><AnimatedNumber value={score} /></div>
          <div style={{ color, fontWeight: 700, fontFamily: "var(--font-display)", fontSize: size * 0.075, marginTop: 4 }}>{label}</div>
          {sub && <div className="hud" style={{ marginTop: 4, fontSize: 9.5 }}>{sub}</div>}
        </div>
      </div>
    </div>
  );
}

// ---------- line / area chart with optional band and hover ----------
export function LineChart({ data, lines, height = 190, yMin, yMax, band, xKey = "date", fmtX = (v) => v.slice(5), fmtY = (v) => Math.round(v), tour }) {
  const W = 640, H = height, P = { l: 8, r: 8, t: 12, b: 4 };
  const ref = useRef(null);
  const [hover, setHover] = useState(null);
  const id = useId().replace(/:/g, "");
  const vals = data.flatMap((d) => lines.map((l) => d[l.key])).filter((v) => v !== null && v !== undefined);
  const lo = yMin ?? Math.min(0, ...vals);
  const hi = yMax ?? Math.max(1, ...vals) * 1.12;
  const x = (i) => P.l + (i / Math.max(1, data.length - 1)) * (W - P.l - P.r);
  const y = (v) => P.t + (1 - (v - lo) / (hi - lo || 1)) * (H - P.t - P.b);
  const paths = useMemo(() => lines.map((l) => {
    let d = "", started = false;
    data.forEach((p, i) => {
      const v = p[l.key];
      if (v === null || v === undefined) { started = false; return; }
      d += `${started ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      started = true;
    });
    const area = l.fill ? `${d}L${x(data.length - 1)},${H}L${x(0)},${H}Z` : null;
    return { ...l, d, area };
  }), [data, lines, lo, hi]); // eslint-disable-line react-hooks/exhaustive-deps
  const onMove = (e) => {
    const rect = ref.current.getBoundingClientRect();
    const i = Math.round(((e.clientX - rect.left) / rect.width) * (data.length - 1));
    setHover(Math.max(0, Math.min(data.length - 1, i)));
  };
  return (
    <div data-tour={tour} style={{ position: "relative" }}>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height }} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        <defs>
          {lines.map((l) => (
            <linearGradient key={l.key} id={`a${id}${l.key}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={l.color} stopOpacity="0.35" /><stop offset="1" stopColor={l.color} stopOpacity="0" /></linearGradient>
          ))}
        </defs>
        {[0.25, 0.5, 0.75].map((f) => <line key={f} x1="0" x2={W} y1={P.t + f * (H - P.t - P.b)} y2={P.t + f * (H - P.t - P.b)} stroke="rgba(255,255,255,0.05)" vectorEffect="non-scaling-stroke" />)}
        {band && <rect x="0" width={W} y={y(band.to)} height={Math.max(0, y(band.from) - y(band.to))} fill={band.color || "rgba(52,211,153,0.08)"} />}
        {paths.map((p) => p.area && <path key={`a${p.key}`} d={p.area} fill={`url(#a${id}${p.key})`} />)}
        {paths.map((p) => <motion.path key={p.key} d={p.d} fill="none" stroke={p.color} strokeWidth={p.width || 2.2} strokeDasharray={p.dashed ? "5 5" : undefined} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.1, ease: "easeOut" }} style={{ filter: p.glow ? `drop-shadow(0 0 6px ${p.color})` : undefined }} />)}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1="0" y2={H} stroke="rgba(255,255,255,0.25)" vectorEffect="non-scaling-stroke" strokeDasharray="3 3" />}
      </svg>
      {band?.label && <div className="pill-src" style={{ position: "absolute", right: 6, top: y(band.to) / H * height - 2 }}>{band.label}</div>}
      <div className="row between" style={{ marginTop: 6 }}>
        {data.filter((_, i) => i % Math.ceil(data.length / 6) === 0 || i === data.length - 1).map((d) => <span key={d[xKey]} className="pill-src">{fmtX(d[xKey])}</span>)}
      </div>
      {hover !== null && (
        <div className="card tight" style={{ position: "absolute", top: 6, left: `${Math.min(72, (hover / Math.max(1, data.length - 1)) * 100)}%`, pointerEvents: "none", fontSize: 12, zIndex: 2, background: "rgba(13,16,36,0.95)" }}>
          <div className="hud">{fmtX(data[hover][xKey])}</div>
          {lines.map((l) => <div key={l.key} className="row" style={{ gap: 6 }}><i style={{ width: 8, height: 8, borderRadius: 2, background: l.color }} />{l.label}: <b>{data[hover][l.key] === null || data[hover][l.key] === undefined ? "–" : fmtY(data[hover][l.key])}</b></div>)}
        </div>
      )}
    </div>
  );
}

// ---------- stacked bars by team with a guideline line ----------
// Stacked bars: days = [{ date, label, overs (total), byTeam: { seriesName: value } }]; limit draws a dashed reference line.
export const SERIES_COLORS = ["#22d3ee", "#8b5cf6", "#ff4d9d", "#fbbf24", "#34d399", "#60a5fa"];
export const TEAM_COLOR = { School: "#22d3ee", Club: "#8b5cf6", District: "#ff4d9d", Match: "#fbbf24" };
export function TeamBars({ days, limit, height = 170, tour, colors = TEAM_COLOR, limitLabel }) {
  const TEAM_COLOR = colors;
  const max = Math.max(limit * 1.25, ...days.map((d) => d.overs || 0), 1);
  return (
    <div data-tour={tour}>
      <div style={{ position: "relative", height, display: "grid", gridTemplateColumns: `repeat(${days.length}, minmax(0,1fr))`, gap: 6, alignItems: "end" }}>
        <div style={{ position: "absolute", left: 0, right: 0, bottom: `${(limit / max) * 100}%`, borderTop: "1.5px dashed rgba(251,113,133,0.6)" }}>
          <span className="pill-src" style={{ position: "absolute", right: 0, top: -16, color: "var(--rose)" }}>{limitLabel ?? `limit ${limit}`}</span>
        </div>
        {days.map((d, i) => (
          <div key={d.date} style={{ height: "100%", display: "flex", flexDirection: "column", justifyContent: "flex-end", gap: 2 }} title={`${d.date}: ${d.overs} overs`}>
            {Object.entries(d.byTeam || {}).filter(([, v]) => v > 0).map(([team, v]) => (
              <motion.div key={team} initial={{ height: 0 }} animate={{ height: `${(v / max) * 100}%` }} transition={{ duration: 0.7, delay: i * 0.04 }}
                style={{ background: TEAM_COLOR[team] || "#888", borderRadius: 5, boxShadow: `0 0 12px ${TEAM_COLOR[team]}55`, minHeight: 3 }} />
            ))}
            {!d.overs && <div style={{ height: 3, borderRadius: 3, background: "rgba(255,255,255,0.08)" }} />}
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${days.length}, minmax(0,1fr))`, gap: 6, marginTop: 8 }}>
        {days.map((d) => <span key={d.date} className="pill-src" style={{ textAlign: "center" }}>{d.label}</span>)}
      </div>
    </div>
  );
}

export function Spark({ values, color = "var(--cyan)", height = 34, width = 110 }) {
  const v = values.map((x) => (x === null || x === undefined ? null : x));
  const nums = v.filter((x) => x !== null);
  if (nums.length < 2) return <svg width={width} height={height} />;
  const lo = Math.min(...nums), hi = Math.max(...nums);
  let d = "", started = false;
  v.forEach((x, i) => {
    if (x === null) { started = false; return; }
    const px = (i / (v.length - 1)) * width, py = height - 3 - ((x - lo) / (hi - lo || 1)) * (height - 6);
    d += `${started ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`;
    started = true;
  });
  return <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}><path d={d} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

// ---------- heatmap (rows × days) ----------
export function Heatmap({ rows, days, max = 12, onRow, tour }) {
  const color = (v) => {
    if (v === null || v === undefined) return "repeating-linear-gradient(135deg, rgba(139,92,246,0.15) 0 4px, transparent 4px 8px)";
    if (v === 0) return "rgba(255,255,255,0.04)";
    const t = Math.min(1, v / max);
    return t > 0.85 ? `rgba(251,113,133,${0.45 + t * 0.5})` : t > 0.55 ? `rgba(255,77,157,${0.3 + t * 0.5})` : `rgba(139,92,246,${0.25 + t * 0.6})`;
  };
  return (
    <div data-tour={tour} style={{ overflowX: "auto" }}>
      <div style={{ display: "grid", gridTemplateColumns: `92px repeat(${days.length}, minmax(18px, 1fr))`, gap: 4, minWidth: 92 + days.length * 22 }}>
        <span />
        {days.map((d) => <span key={d} className="pill-src" style={{ textAlign: "center", fontSize: 9.5 }}>{d.slice(8)}</span>)}
        {rows.map((r) => (
          <FragmentRow key={r.id} r={r} color={color} onRow={onRow} />
        ))}
      </div>
    </div>
  );
}
function FragmentRow({ r, color, onRow }) {
  return (
    <>
      <button className="small" onClick={() => onRow?.(r.id)} style={{ textAlign: "left", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: "var(--text-2)" }}>{r.name}</button>
      {r.cells.map((v, i) => <span key={i} title={v === null ? "private" : `${v} overs`} style={{ height: 22, borderRadius: 5, background: color(v) }} />)}
    </>
  );
}

// ---------- radial mini ring ----------
export function MiniRing({ value, max = 1, color = "var(--pink)", size = 54, label }) {
  const r = 22, c = 2 * Math.PI * r;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg viewBox="0 0 54 54" width={size} height={size}>
        <circle cx="27" cy="27" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="5" />
        <motion.circle cx="27" cy="27" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round" transform="rotate(-90 27 27)"
          initial={{ strokeDasharray: `0 ${c}` }} animate={{ strokeDasharray: `${(c * Math.min(1, value / max))} ${c}` }} transition={{ duration: 1 }} />
      </svg>
      <div className="center" style={{ position: "absolute", inset: 0, fontSize: 11.5, fontWeight: 700 }}>{label}</div>
    </div>
  );
}

export const StackedBars = TeamBars;
