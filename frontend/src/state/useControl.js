// Control-room live state from /ws/control: incidents, KPIs and live calls. Reconnects.
import { useEffect, useState } from "react";
import { wsUrl } from "../net/callSocket";

const RANK = { critical: 0, high: 1, medium: 2, low: 3 };
export const sortQueue = (list) =>
  [...list].sort((a, b) => (a.status === "resolved") - (b.status === "resolved")
    || RANK[a.severity.level] - RANK[b.severity.level] || b.severity.score - a.severity.score);

export function useControl() {
  const [incidents, setIncidents] = useState([]);
  const [kpis, setKpis] = useState(null);
  const [liveCalls, setLiveCalls] = useState([]);
  const [online, setOnline] = useState(false);

  useEffect(() => {
    let ws;
    let timer;
    let stopped = false;
    const connect = () => {
      ws = new WebSocket(wsUrl("/ws/control"));
      ws.onopen = () => setOnline(true);
      ws.onclose = () => {
        setOnline(false);
        if (!stopped) timer = setTimeout(connect, 1500);
      };
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        switch (m.type) {
          case "snapshot":
            setIncidents(m.incidents);
            setKpis(m.kpis);
            setLiveCalls(m.live_calls);
            break;
          case "incident": {
            const inc = m.incident;
            // a merged-away incident's callers all appear in the incident that absorbed it
            setIncidents((list) => [...list.filter((i) => i.id !== inc.id
              && !i.call_ids.every((c) => inc.call_ids.includes(c))), inc]);
            break;
          }
          case "kpis":
            setKpis(m);
            break;
          case "call_started":
            setLiveCalls((c) => [...new Set([...c, m.call_id])]);
            break;
          case "call_ended":
            setLiveCalls((c) => c.filter((x) => x !== m.call_id));
            break;
          default:
            break;
        }
      };
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return { incidents: sortQueue(incidents), kpis, liveCalls, online };
}
