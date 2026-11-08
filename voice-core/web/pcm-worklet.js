// AudioWorklet: downsample the mic to `targetRate` and post 512-sample Int16 frames
// (1024 bytes, exactly what Gnani Prisma's realtime STT expects).
// A box filter over each output period acts as a cheap anti-alias low-pass.
class PcmCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const o = (options && options.processorOptions) || {};
    this.targetRate = o.targetRate || 8000;
    this.frameSamples = o.frameSamples || 512;
    this.ratio = sampleRate / this.targetRate; // input samples per output sample (sampleRate is a worklet global)
    this.acc = 0;
    this.count = 0;
    this.t = 0;
    this.frame = new Int16Array(this.frameSamples);
    this.fi = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input.length) return true;
    const ch = input[0];
    for (let i = 0; i < ch.length; i++) {
      this.acc += ch[i];
      this.count += 1;
      this.t += 1;
      if (this.t >= this.ratio) {
        this.t -= this.ratio;
        let s = this.acc / this.count;
        this.acc = 0;
        this.count = 0;
        s = s < -1 ? -1 : s > 1 ? 1 : s;
        this.frame[this.fi++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        if (this.fi === this.frameSamples) {
          const out = this.frame;
          this.port.postMessage(out.buffer, [out.buffer]);
          this.frame = new Int16Array(this.frameSamples);
          this.fi = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCapture);
