// Static demo (npm run build:demo): no backend. GETs come from JSON snapshots of a real live run
// (public/demo/, refreshed by scripts/snapshot_demo.py); the two WebSockets replay recorded timelines.
// The app's own code is untouched: fetch and WebSocket are swapped for /api and /ws URLs only.

export const DEMO = import.meta.env.VITE_DEMO === "1";
export const REPO_URL = "https://github.com/nitya-prakash-pandey-2005/pukaar";

const realFetch = window.fetch.bind(window);
const RealWS = window.WebSocket;
const TO_CONTROL = new Set(["incident", "language"]);

let dataPromise = null;
const load = () => (dataPromise ||= Promise.all(
  ["control", "call", "broadcast", "sms"].map((n) => realFetch(`/demo/${n}.json`).then((r) => r.json())),
).then(([control, call, broadcast, sms]) => ({ control, call, broadcast, sms })));

// ---------------------------------------------------------------- control-room state shared by all sockets
const room = { incidents: new Map(), kpis: null, liveCalls: new Set(), sockets: new Set(), surgeTimers: [] };
let roomReady = null;
const initRoom = () => (roomReady ||= load().then(({ control }) => setSnapshot(control.snapshot, false)));

function setSnapshot(snap, send = true) {
  room.incidents = new Map(snap.incidents.map((i) => [i.id, i]));
  room.kpis = snap.kpis;
  if (send) room.sockets.forEach((s) => s.emit(snapshotMsg()));
}
const snapshotMsg = () => ({ type: "snapshot", incidents: [...room.incidents.values()], kpis: room.kpis,
  live_calls: [...room.liveCalls] });

function toRoom(msg) {
  if (msg.type === "incident") room.incidents.set(msg.incident.id, msg.incident);
  if (msg.type === "kpis") room.kpis = (({ type, ...k }) => k)(msg);
  if (msg.type === "call_started") room.liveCalls.add(msg.call_id);
  if (msg.type === "call_ended") room.liveCalls.delete(msg.call_id);
  room.sockets.forEach((s) => s.emit(msg));
}

function roomKpis() { // after a dispatcher action: same counts the server computes (store.kpis)
  const open = [...room.incidents.values()].filter((i) => i.status !== "resolved");
  return { type: "kpis", ...room.kpis, critical_open: open.filter((i) => i.severity.level === "critical").length,
    people_affected: open.reduce((n, i) => n + (i.facts.people_count || 1), 0) };
}

// ---------------------------------------------------------------- WebSocket replay
class DemoSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.binaryType = "blob";
    this.bufferedAmount = 0;
    this.onopen = this.onmessage = this.onclose = this.onerror = null;
    this.kind = url.includes("/ws/control") ? "control" : "call";
    this.timers = [];
    if (this.kind === "call") {
      this.t0 = performance.now();
      // created inside the "Call Pukaar" click, so the browser lets it play: the synthetic caller's own voice
      this.caller = new Audio("/demo/audio/caller.wav");
      this.caller.play().catch(() => {});
    }
    setTimeout(() => this.open(), 30);
  }

  async open() {
    if (this.readyState !== 0) return;
    if (this.kind === "control") await initRoom();
    this.readyState = 1;
    this.onopen?.({});
    if (this.kind === "control") {
      room.sockets.add(this);
      this.emit(snapshotMsg());
    } else {
      this.replayCall();
    }
  }

  emit(m) {
    if (this.readyState !== 1) return;
    this.onmessage?.({ data: m instanceof ArrayBuffer ? m : JSON.stringify(m) });
  }

  at(seconds, fn) {
    const wait = Math.max(0, seconds * 1000 - (performance.now() - this.t0));
    this.timers.push(setTimeout(fn, wait));
  }

  async replayCall() {
    const [{ call }, greeting] = await Promise.all([load(), realFetch("/demo/audio/greeting.pcm")
      .then((r) => (r.ok ? r.arrayBuffer() : null)).catch(() => null), initRoom()]);
    this.call = call;
    toRoom({ type: "call_started", call_id: call.call_id });
    for (const { t, msg } of call.events) {
      this.at(t, () => {
        this.emit(msg);
        if (TO_CONTROL.has(msg.type)) toRoom({ ...msg, call_id: call.call_id });
        if (msg.type === "turn" && msg.speaker === "pukaar" && t < 1 && greeting) this.emit(greeting.slice(0));
      });
    }
    this.at(call.seconds, () => this.end());
  }

  end() {
    if (this.readyState !== 1 || this.kind !== "call") return;
    this.timers.forEach(clearTimeout);
    this.caller?.pause();
    const seconds = Math.round((performance.now() - this.t0) / 100) / 10;
    this.emit({ type: "agent_speaking", on: false });
    this.emit({ type: "call_ended", call_id: this.call?.call_id, seconds });
    if (this.call) {
      toRoom({ type: "call_ended", call_id: this.call.call_id });
      toRoom({ type: "incident", incident: this.call.final_incident }); // back to the recorded end state
    }
    this.close();
  }

  send(data) {
    if (this.kind !== "call" || typeof data !== "string") return; // mic audio is never captured in the demo
    try {
      // async like a real socket: the app sets "ending" right after sending, then the server's reply arrives
      if (JSON.parse(data).type === "hangup") setTimeout(() => this.end(), 150);
    } catch { /* ignore */ }
  }

  close() {
    if (this.readyState === 3) return;
    this.timers.forEach(clearTimeout);
    this.caller?.pause();
    room.sockets.delete(this);
    this.readyState = 3;
    this.onclose?.({ code: 1000 });
  }
}

function DemoAwareWebSocket(url, protocols) {
  return /\/ws\/(control|call)$/.test(String(url)) ? new DemoSocket(String(url)) : new RealWS(url, protocols);
}
Object.assign(DemoAwareWebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });

// ---------------------------------------------------------------- REST
const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { "Content-Type": "application/json" } });
const live = (what) => json({ detail: `Demo replay: ${what} needs the live server. Run Pukaar locally with your own keys.` }, 503);

async function surge() {
  const { control } = await load();
  await initRoom();
  if (room.surgeTimers.length) return json({ detail: "a surge is already running" }, 409);
  const { before, events } = control.surge;
  setSnapshot(before);
  const t0 = performance.now();
  for (const { t, msg } of events) {
    room.surgeTimers.push(setTimeout(() => toRoom(msg), Math.max(0, t * 1000 - (performance.now() - t0))));
  }
  const last = events.length ? events[events.length - 1].t : 0;
  room.surgeTimers.push(setTimeout(() => { room.surgeTimers = []; }, last * 1000 + 100));
  return json({ started: events.filter((e) => e.msg.type === "incident").length, mode: "replay" });
}

function update(id, patch) {
  const inc = room.incidents.get(id);
  if (!inc) return json({ detail: "incident not found" }, 404);
  const next = { ...inc, ...patch, updated_at: Date.now() / 1000 };
  toRoom({ type: "incident", incident: next });
  toRoom(roomKpis());
  return json(next);
}

async function post(path, body) {
  const data = await load();
  await initRoom();
  let m;
  if (path === "/api/surge") return surge();
  if ((m = path.match(/^\/api\/incidents\/([\w-]+)\/dispatch$/))) {
    return update(m[1], { status: "dispatched", dispatch: { team: body.team, note: body.note || "", eta: body.eta ?? null } });
  }
  if ((m = path.match(/^\/api\/incidents\/([\w-]+)\/resolve$/))) return update(m[1], { status: "resolved" });
  if (/^\/api\/incidents\/[\w-]+\/message$/.test(path)) return live("translating a dispatcher's message");
  if (path === "/api/sms") {
    const text = String(body.text || "").trim();
    const rec = data.sms.find((s) => s.text.trim() === text);
    if (rec) return json({ incident: rec.incident, reply: rec.reply });
    const first = data.sms[0];
    if (!first) return live("SMS triage");
    return json({ incident: first.incident,
      reply: `Demo replay: SMS triage needs the live server. Recorded reply to a Tamil SMS in the live run: ${first.reply}` });
  }
  if (path === "/api/missed-call") {
    const now = Date.now() / 1000;
    const callId = `demo${Math.random().toString(16).slice(2, 10)}`;
    const gps = Array.isArray(body.gps) ? body.gps : null;
    const incident = {
      id: `demo${Math.random().toString(16).slice(2, 10)}`, call_ids: [callId],
      facts: { locality: null, landmark: null, lat: null, lon: null, hazard: null, people_count: null, trapped: null,
        on_roof: null, water_level: null, vulnerable: [], injuries: [], medical_needs: [], needs: [], caller_language: null },
      lat: gps?.[0] ?? null, lon: gps?.[1] ?? null, loc_source: gps ? "gps" : "", loc_confidence: gps ? 0.7 : 0,
      severity: { score: 0, level: "low", drivers: [] }, status: "new", dispatch: null, guidance_given: [],
      channel: "missed_call", created_at: now, updated_at: now,
    };
    toRoom({ type: "incident", incident });
    return json({ call_id: callId, incident });
  }
  if (path === "/api/broadcast") {
    const want = new Set(body.langs || []);
    const items = data.broadcast.filter((i) => want.has(i.lang));
    if (!items.length) return live("translating and speaking these languages (the recording has Tamil, Hindi, Telugu and English)");
    return json(items);
  }
  if (path === "/api/broadcast/cap") return realFetch("/demo/cap.xml");
  return live("this action");
}

// Decision-support snapshots were computed from the recorded incidents; after a dispatcher acts in this browser,
// a team now on a job is busy (as allocate.live_status computes it) and a handled incident leaves the plan.
function busyNow() {
  return new Set([...room.incidents.values()].filter((i) => i.status === "dispatched" && i.dispatch).map((i) => i.dispatch.team));
}
const ADJUST = [
  [/^\/api\/teams$/, (ts) => { const b = busyNow(); return ts.map((t) => ({ ...t, status: t.roster_status === "busy" || b.has(t.name) ? "busy" : "available" })); }],
  [/^\/api\/incidents\/[\w-]+\/recommend$/, (r) => {
    const b = busyNow();
    const recommendations = r.recommendations.filter((x) => !b.has(x.team));
    return { ...r, recommendations, teams_free: Math.max(0, r.teams_free - (r.recommendations.length - recommendations.length)) };
  }],
  [/^\/api\/plan$/, (p) => {
    const b = busyNow();
    const waiting = (id) => room.incidents.get(id)?.status === "new";
    return { ...p, assignments: p.assignments.filter((a) => waiting(a.incident_id) && !b.has(a.team)),
      unassigned: p.unassigned.filter((u) => waiting(u.incident_id)), teams_free: p.teams_free.filter((t) => !b.has(t)) };
  }],
];

async function demoGet(path) {
  const r = await realFetch(`/demo${path}.json`);
  const adjust = r.ok && ADJUST.find(([re]) => re.test(path))?.[1];
  if (!adjust) return r;
  await initRoom();
  return json(adjust(await r.json()));
}

function demoFetch(input, init = {}) {
  const url = new URL(typeof input === "string" ? input : input.url, window.location.href);
  if (url.origin !== window.location.origin || !url.pathname.startsWith("/api/")) return realFetch(input, init);
  const method = (init.method || (typeof input === "string" ? "GET" : input.method) || "GET").toUpperCase();
  if (method === "GET") return demoGet(url.pathname);
  let body = {};
  try { body = init.body ? JSON.parse(init.body) : {}; } catch { /* empty body */ }
  return post(url.pathname, body);
}

export function installDemo() {
  window.fetch = demoFetch;
  window.WebSocket = DemoAwareWebSocket;
  load().catch(() => {});
  // an older build's service worker could keep serving stale files: the demo never uses one
  navigator.serviceWorker?.getRegistrations?.().then((rs) => rs.forEach((r) => r.unregister())).catch(() => {});
}

