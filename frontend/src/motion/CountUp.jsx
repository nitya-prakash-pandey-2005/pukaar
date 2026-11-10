import { useLayoutEffect, useRef } from "react";
import { animate } from "animejs";

// A number that counts from its previous value to the new one (anime.js). The span's text is owned here, not by React,
// so React never writes into a text node the animation replaced. Non-numbers ("–") and reduced motion show as-is.
const decimals = (v) => (String(v).split(".")[1] || "").length;
const reduce = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function CountUp({ value }) {
  const ref = useRef(null);
  const prev = useRef(0);
  useLayoutEffect(() => {
    const el = ref.current;
    const to = typeof value === "number" ? value : parseFloat(value);
    if (!el) return;
    if (!Number.isFinite(to) || reduce()) { el.textContent = String(value); prev.current = Number.isFinite(to) ? to : 0; return; }
    const dec = decimals(value);
    const o = { v: prev.current };
    prev.current = to;
    const a = animate(o, { v: to, duration: 1100, ease: "outExpo", onUpdate: () => { el.textContent = o.v.toFixed(dec); }, onComplete: () => { el.textContent = String(value); } });
    return () => { a.pause(); el.textContent = String(value); };
  }, [value]);
  return <span ref={ref} className="count-up" />;
}
