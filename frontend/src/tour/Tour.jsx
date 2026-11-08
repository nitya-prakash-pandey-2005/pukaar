import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronLeft, ChevronRight, Pause, Play, Volume2, VolumeX, X } from "lucide-react";
import { useTour, next, prev, stop, togglePlay, toggleNarrate, getSteps } from "./engine";

function useRect(target) {
  const [rect, setRect] = useState(null);
  useEffect(() => {
    if (!target) { setRect(null); return; }
    let raf;
    const loop = () => {
      const el = document.querySelector(`[data-tour="${target}"]`);
      if (el) {
        const r = el.getBoundingClientRect();
        setRect((old) => (old && Math.abs(old.top - r.top) < 0.5 && Math.abs(old.left - r.left) < 0.5 && Math.abs(old.width - r.width) < 0.5 && Math.abs(old.height - r.height) < 0.5 ? old : { top: r.top, left: r.left, width: r.width, height: r.height }));
      } else setRect(null);
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return rect;
}

export default function Tour() {
  const t = useTour();
  const steps = getSteps();
  const rect = useRect(t.active ? t.target : null);
  const [, force] = useState(0);
  useEffect(() => { if (!t.active) return; const i = setInterval(() => force((x) => x + 1), 120); return () => clearInterval(i); }, [t.active]);
  useEffect(() => {
    if (!t.active) return;
    const k = (e) => { if (e.key === "Escape") stop(); if (e.key === "ArrowRight") next(); if (e.key === "ArrowLeft") prev(); if (e.key === " ") { e.preventDefault(); togglePlay(); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [t.active]);
  if (!t.active) return null;
  const step = steps[t.index];
  const elapsed = t.duration ? Math.min(1, (Date.now() - t.stepStarted) / t.duration) : 0;
  const pad = 10;
  return (
    <div className="tour-root" aria-live="polite">
      {rect ? (
        <motion.div className="tour-spot" initial={false}
          animate={{ top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }}
          transition={{ type: "spring", stiffness: 220, damping: 30 }} />
      ) : <div className="tour-dim" />}
      <AnimatePresence mode="wait">
        <motion.div key={t.index} className="tour-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.3 }}>
          <div className="row between">
            <span className="hud c-pink">Guided tour · {t.index + 1}/{steps.length}</span>
            <button className="btn icon sm ghost" onClick={stop} aria-label="Exit tour"><X size={15} /></button>
          </div>
          <h3 style={{ marginTop: 6, fontSize: 18 }}>{step.title}</h3>
          <p className="text-2" style={{ marginTop: 6, fontSize: 14 }}>{step.body}</p>
          <div className="progress" style={{ marginTop: 12, height: 4 }}><i style={{ width: `${elapsed * 100}%` }} /></div>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn icon sm" onClick={prev} disabled={t.index === 0} aria-label="Previous"><ChevronLeft size={16} /></button>
            <button className="btn sm" onClick={togglePlay}>{t.playing ? <><Pause size={15} />Pause</> : <><Play size={15} />Play</>}</button>
            <button className="btn icon sm" onClick={next} aria-label="Next"><ChevronRight size={16} /></button>
            <span className="grow" />
            <button className="btn icon sm ghost" onClick={toggleNarrate} aria-label="Narration">{t.narrate ? <Volume2 size={16} /> : <VolumeX size={16} />}</button>
          </div>
          <div className="tour-dots">{steps.map((_, i) => <i key={i} className={i < t.index ? "done" : i === t.index ? "on" : ""} />)}</div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
