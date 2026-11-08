// WebSocket client for /ws/call (protocol: backend/pukaar/app.py).
// openCall({ gps, noiseSnrDb, onEvent, onAudio, onClose }) -> { sendAudio, setNoise, hangup, close }

export const wsUrl = (path) => `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${path}`;

export function openCall({ gps = null, noiseSnrDb = null, onEvent, onAudio, onClose } = {}) {
  const ws = new WebSocket(wsUrl("/ws/call"));
  ws.binaryType = "arraybuffer";
  let closed = false;

  ws.onopen = () => ws.send(JSON.stringify({ type: "start", gps, noise_snr_db: noiseSnrDb }));
  ws.onmessage = (e) => {
    if (typeof e.data === "string") {
      try { onEvent?.(JSON.parse(e.data)); } catch { /* ignore malformed */ }
    } else {
      onAudio?.(e.data);
    }
  };
  ws.onerror = () => onEvent?.({ type: "status", stt: "error", message: "Connection to the Pukaar server failed" });
  ws.onclose = () => {
    if (closed) return;
    closed = true;
    onClose?.();
  };

  const isOpen = () => ws.readyState === WebSocket.OPEN;
  return {
    sendAudio(ab) {
      // drop audio rather than queue it up on a slow network (realtime beats completeness)
      if (isOpen() && ws.bufferedAmount < 256 * 1024) ws.send(ab);
    },
    setNoise(db) {
      if (isOpen()) ws.send(JSON.stringify({ type: "set_noise", snr_db: db }));
    },
    hangup() {
      if (isOpen()) ws.send(JSON.stringify({ type: "hangup" }));
      setTimeout(() => { try { ws.close(); } catch { /* already closed */ } }, 5000);
    },
    close() {
      try { ws.close(); } catch { /* already closed */ }
    },
  };
}
