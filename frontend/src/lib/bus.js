// Tiny event bus used by the guided tour to drive page-level animations (e.g. live voice typing).
const target = typeof window !== "undefined" ? window : null;
export const emitBus = (cmd, detail = {}) => target?.dispatchEvent(new CustomEvent("sakhi:bus", { detail: { cmd, ...detail } }));
export function onBus(handler) {
  const fn = (e) => handler(e.detail);
  target?.addEventListener("sakhi:bus", fn);
  return () => target?.removeEventListener("sakhi:bus", fn);
}
