// Gapless player for streamed Int16 PCM chunks (Dadi's voice from Gnani Timbre).
// createPcmPlayer({ sampleRate }) -> { play(arrayBuffer), flush(), level(), busy(), close() }
// Create it from a user gesture (a click), so the browser allows audio.

const JITTER_S = 0.06; // small buffer so network jitter doesn't cause clicks

export function createPcmPlayer({ sampleRate = 8000 } = {}) {
  const ctx = new AudioContext();
  const gain = ctx.createGain();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  gain.connect(analyser);
  analyser.connect(ctx.destination);
  const scratch = new Float32Array(analyser.fftSize);
  const sources = new Set();
  let nextTime = 0;
  let carry = null; // odd trailing byte from the previous chunk

  function play(ab) {
    if (!ab || !ab.byteLength) return;
    if (ctx.state === "suspended") ctx.resume();
    let bytes = new Uint8Array(ab);
    if (carry) {
      const merged = new Uint8Array(carry.length + bytes.length);
      merged.set(carry);
      merged.set(bytes, carry.length);
      bytes = merged;
      carry = null;
    }
    if (bytes.length % 2) {
      carry = bytes.slice(bytes.length - 1);
      bytes = bytes.slice(0, bytes.length - 1);
    }
    if (!bytes.length) return;
    const i16 = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.length / 2);
    const f32 = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;
    const buf = ctx.createBuffer(1, f32.length, sampleRate);
    buf.copyToChannel(f32, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(gain);
    const now = ctx.currentTime;
    if (nextTime < now + 0.005) nextTime = now + JITTER_S; // (re)start after an underrun
    src.start(nextTime);
    nextTime += buf.duration;
    sources.add(src);
    src.onended = () => sources.delete(src);
  }

  function flush() {
    for (const s of sources) {
      try { s.stop(); } catch { /* not started yet */ }
    }
    sources.clear();
    nextTime = 0;
    carry = null;
  }

  function level() {
    analyser.getFloatTimeDomainData(scratch);
    let s = 0;
    for (let i = 0; i < scratch.length; i++) s += scratch[i] * scratch[i];
    return Math.min(1, Math.sqrt(s / scratch.length) * 6);
  }

  return {
    play,
    flush,
    level,
    busy: () => nextTime > ctx.currentTime,
    close: () => { flush(); ctx.close().catch(() => {}); },
    context: ctx,
  };
}
