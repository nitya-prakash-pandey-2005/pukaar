// Voice in (Web Speech recognition, Hindi by default) and voice out (narration / Didi Talks).
const Rec = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
export const canListen = () => !!Rec;
export const canSpeak = () => typeof window !== "undefined" && !!window.speechSynthesis;

export function listen({ lang = "hi-IN", onText, onEnd, onError }) {
  if (!Rec) { onError?.(new Error("Speech recognition not supported")); return () => {}; }
  const r = new Rec();
  r.lang = lang;
  r.interimResults = true;
  r.continuous = false;
  r.onresult = (e) => {
    const t = Array.from(e.results).map((x) => x[0].transcript).join(" ");
    onText?.(t, e.results[e.results.length - 1].isFinal);
  };
  r.onerror = (e) => onError?.(e);
  r.onend = () => onEnd?.();
  r.start();
  return () => { try { r.stop(); } catch { /* already stopped */ } };
}

let voices = [];
if (canSpeak()) {
  const load = () => { voices = window.speechSynthesis.getVoices(); };
  load();
  window.speechSynthesis.onvoiceschanged = load;
}

export function speak(text, { lang = "en-IN", rate = 1, onEnd } = {}) {
  if (!canSpeak()) { onEnd?.(); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  u.rate = rate;
  const pref = voices.find((v) => v.lang === lang && /female|heera|swara|neerja|kalpana|google/i.test(v.name)) || voices.find((v) => v.lang === lang) || voices.find((v) => v.lang.startsWith(lang.split("-")[0]));
  if (pref) u.voice = pref;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

export function stopSpeaking() { if (canSpeak()) window.speechSynthesis.cancel(); }
