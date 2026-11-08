// Microphone capture -> Int16 PCM frames at `targetRate` (default 8 kHz, phone quality).
// startMic({ targetRate, onFrame }) -> Promise<{ stop(), level() }>
// onFrame(ArrayBuffer) receives 512-sample Int16 frames.

export async function startMic({ targetRate = 8000, onFrame, frameSamples = 512 } = {}) {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser cannot access the microphone.");
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: true, channelCount: 1 },
  });
  const ctx = new AudioContext();
  if (ctx.state === "suspended") await ctx.resume();
  await ctx.audioWorklet.addModule(new URL("./pcm-worklet.js", import.meta.url));
  const src = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, "pcm-capture", { processorOptions: { targetRate, frameSamples } });
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  const buf = new Float32Array(analyser.fftSize);
  node.port.onmessage = (e) => onFrame?.(e.data);
  src.connect(node);
  src.connect(analyser);
  // keep the worklet pulled by the graph without making any sound
  const mute = ctx.createGain();
  mute.gain.value = 0;
  node.connect(mute).connect(ctx.destination);

  let stopped = false;
  return {
    level() {
      analyser.getFloatTimeDomainData(buf);
      let s = 0;
      for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
      return Math.min(1, Math.sqrt(s / buf.length) * 5);
    },
    stop() {
      if (stopped) return;
      stopped = true;
      node.port.onmessage = null;
      try { src.disconnect(); node.disconnect(); } catch { /* already gone */ }
      stream.getTracks().forEach((t) => t.stop());
      ctx.close().catch(() => {});
    },
  };
}
