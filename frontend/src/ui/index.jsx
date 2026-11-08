import { useEffect, useState, useSyncExternalStore } from "react";
import { AnimatePresence, motion, animate } from "motion/react";
import { Lock, X, CheckCircle2, AlertTriangle, Info } from "lucide-react";
export const initials = (name = "") => name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
export const hueOf = (h) => `linear-gradient(135deg, hsl(${h} 85% 60%), hsl(${(h + 50) % 360} 80% 52%))`;

export function Card({ title, icon: Icon, right, children, className = "", tour, ...rest }) {
  return (
    <section className={`card ${className}`} data-tour={tour} {...rest}>
      {(title || right) && (
        <div className="card-head">
          {Icon && <span className="ic"><Icon size={17} /></span>}
          {title && <h3>{title}</h3>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export const Hud = ({ children, tone, className = "" }) => <span className={`hud ${tone ? `c-${tone}` : ""} ${className}`}>{children}</span>;

export function Badge({ tone = "muted", dot, children, className = "" }) {
  return <span className={`badge t-${tone} ${className}`}>{dot && <span className="dot" />}{children}</span>;
}

export function SignalBadge({ signal }) {
  if (!signal) return null;
  return <Badge tone={signal.tone === "muted" ? "muted" : signal.tone === "pink" ? "rose" : signal.tone} dot>{signal.label}</Badge>;
}

export const BAND_TONE = { primed: "cyan", ready: "green", steady: "amber", recover: "rose" };
export const BAND_COLOR = { primed: "var(--cyan)", ready: "var(--green)", steady: "var(--amber)", recover: "var(--rose)" };

export function Seg({ options, value, onChange, className = "" }) {
  return (
    <div className={`seg ${className}`} role="tablist">
      {options.map((o) => {
        const v = typeof o === "object" ? o.value : o;
        const l = typeof o === "object" ? o.label : o;
        return <button key={v} type="button" role="tab" aria-selected={value === v} className={value === v ? "on" : ""} onClick={() => onChange(v)}>{l}</button>;
      })}
    </div>
  );
}

export function Toggle({ on, onChange, disabled, label }) {
  return <button type="button" className={`toggle ${on ? "on" : ""}`} aria-pressed={on} aria-label={label} disabled={disabled} onClick={() => onChange?.(!on)} />;
}

export function Avatar({ name, hue = 300, size = "", status }) {
  return (
    <span className={`avatar ${size}`} style={{ background: hueOf(hue) }}>
      {initials(name)}
      {status && <span className="status" style={{ background: status }} />}
    </span>
  );
}

export function Stat({ value, unit, label, tone, className = "" }) {
  return (
    <div className={`stat ${className}`}>
      <div className="v" style={tone ? { color: `var(--${tone})` } : undefined}>{value}{unit && <small>{unit}</small>}</div>
      <div className="l">{label}</div>
    </div>
  );
}

export function Redacted({ cls, who = "her", children }) {
  return (
    <div className="redacted">
      <Lock size={16} />
      <span>{children || <>Private: <b>{cls}</b> is not shared with you{who && who !== "her" ? ` by ${who}` : ""}.</>}</span>
    </div>
  );
}

export function Drivers({ drivers = [], max = 2 }) {
  const top = drivers.filter((d) => Math.abs(d.contribution) >= 0.05).slice(0, 6);
  if (!top.length) return <div className="small muted">No single factor stands out today.</div>;
  return (
    <div className="drivers">
      {top.map((d) => {
        const w = Math.min(50, (Math.abs(d.contribution) / max) * 50);
        const pos = d.contribution > 0;
        return (
          <div className="driver" key={d.feature}>
            <span className="text-2" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.label}</span>
            <span className="bar"><span className="mid" />
              <i style={{ left: pos ? "50%" : `${50 - w}%`, width: `${w}%`, background: pos ? "linear-gradient(90deg,#ff4d9d,#fb7185)" : "linear-gradient(90deg,#22d3ee,#34d399)" }} />
            </span>
            <span className="val">{pos ? "+" : "−"}{Math.abs(d.contribution).toFixed(2)}</span>
          </div>
        );
      })}
    </div>
  );
}

export function Progress({ value, color }) {
  return <div className="progress"><i style={{ width: `${Math.max(0, Math.min(100, value))}%`, ...(color ? { background: color } : {}) }} /></div>;
}

export function AnimatedNumber({ value, decimals = 0, suffix = "" }) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const c = animate(v, value, { duration: 0.9, ease: [0.22, 1, 0.36, 1], onUpdate: setV });
    return () => c.stop();
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  return <>{Number(v).toFixed(decimals)}{suffix}</>;
}

export function PageHead({ kicker, title, sub, right, tour }) {
  return (
    <div className="page-head" data-tour={tour}>
      <div className="grow">
        {kicker && <Hud tone="pink">{kicker}</Hud>}
        <h1 style={{ marginTop: kicker ? 6 : 0 }}>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Sheet({ open, onClose, children, title }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside className="sheet right" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 40 }} transition={{ type: "spring", damping: 30, stiffness: 300 }}>
            <div className="row between" style={{ padding: "18px 20px 6px" }}>
              <h2>{title}</h2>
              <button className="btn icon sm ghost" onClick={onClose} aria-label="Close"><X size={16} /></button>
            </div>
            <div style={{ padding: "8px 20px 24px" }}>{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

// ---------- toasts ----------
let toasts = [];
const tl = new Set();
const temit = () => tl.forEach((f) => f());
export function toast(text, tone = "info") {
  const id = Math.random().toString(36).slice(2);
  toasts = [...toasts, { id, text, tone }];
  temit();
  setTimeout(() => { toasts = toasts.filter((t) => t.id !== id); temit(); }, 3400);
}
export function Toasts() {
  const list = useSyncExternalStore((f) => { tl.add(f); return () => tl.delete(f); }, () => toasts);
  const ICON = { info: Info, ok: CheckCircle2, warn: AlertTriangle };
  return (
    <div className="toasts">
      <AnimatePresence>
        {list.map((t) => {
          const I = ICON[t.tone] || Info;
          return (
            <motion.div key={t.id} className="toast" initial={{ opacity: 0, y: 16, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8 }}>
              <I size={17} color={t.tone === "ok" ? "var(--green)" : t.tone === "warn" ? "var(--amber)" : "var(--cyan)"} />{t.text}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

export const Fade = ({ children, delay = 0, className = "", ...rest }) => (
  <motion.div className={className} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay, ease: [0.22, 1, 0.36, 1] }} {...rest}>{children}</motion.div>
);

export const pct = (p, d = 1) => `${(p * 100).toFixed(d)}%`;
