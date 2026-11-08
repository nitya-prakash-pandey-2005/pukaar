// WAV helpers for the browser.
// pcmToWav(int16Array, sampleRate) -> Blob (audio/wav, mono 16-bit)
// decodeToPcm16(fileOrBlob, targetRate) -> Promise<Int16Array> (decodes .wav/.mp3/.ogg/.opus, mixes to mono, resamples)

export function pcmToWav(int16, sampleRate) {
  const dataLen = int16.length * 2;
  const buf = new ArrayBuffer(44 + dataLen);
  const v = new DataView(buf);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF");
  v.setUint32(4, 36 + dataLen, true);
  str(8, "WAVE");
  str(12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); // PCM
  v.setUint16(22, 1, true); // mono
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  str(36, "data");
  v.setUint32(40, dataLen, true);
  new Int16Array(buf, 44).set(int16);
  return new Blob([buf], { type: "audio/wav" });
}

export async function decodeToPcm16(fileOrBlob, targetRate = 16000) {
  const bytes = await fileOrBlob.arrayBuffer();
  const tmp = new OfflineAudioContext(1, 1, 44100);
  let decoded;
  try {
    decoded = await tmp.decodeAudioData(bytes.slice(0));
  } catch {
    throw new Error("Could not decode this audio file. Please export it as MP3 or WAV.");
  }
  const frames = Math.max(1, Math.ceil(decoded.duration * targetRate));
  const off = new OfflineAudioContext(1, frames, targetRate);
  const src = off.createBufferSource();
  src.buffer = decoded; // multi-channel input is down-mixed to the mono destination
  src.connect(off.destination);
  src.start();
  const rendered = await off.startRendering();
  const f32 = rendered.getChannelData(0);
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}
