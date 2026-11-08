"""Live smoke test for Gnani Prisma + Timbre (+ the LLM).

Run from a repo root:   uv run python voice-core/scripts/smoke_gnani.py [--llm] [--voices]
Needs GNANI_API_KEY (and GROQ_API_KEY for --llm) in .env. Uses only a few short sentences of credits.
--voices also renders one Dadi line in all 13 Timbre v3.0 voices into cache/voices/ for picking by ear.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

import numpy as np

from voice_core.audio import float_to_pcm16, pcm16_to_float, wav_bytes
from voice_core.config import get_settings
from voice_core.gnani import PrismaStream, transcribe_rest, tts_rest, tts_stream

LINE = "नमस्ते बेटा, मैं कमला देवी बोल रही हूँ। आपका UPI ID क्या है?"
V3_VOICES = ["Shivani", "Lakshmi", "Kalpana", "Chetana", "Vasudha", "Riyaa", "Tarika",
             "Avinash", "Prakash", "Harshad", "Devansh", "Shubham", "Yashraj"]
results: list[tuple[str, bool, str]] = []


def report(name: str, ok: bool, info: str) -> None:
    results.append((name, ok, info))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {info}", flush=True)


async def main(args) -> int:
    s = get_settings()
    if not s.gnani_api_key:
        print("GNANI_API_KEY missing in .env")
        return 2
    s.cache_dir.mkdir(parents=True, exist_ok=True)
    key = s.gnani_api_key
    pcm = b""

    # 1. TTS REST
    try:
        t0 = time.perf_counter()
        pcm = await tts_rest(key, LINE, voice="Lakshmi", language="hi-IN", sample_rate=8000)
        dt = time.perf_counter() - t0
        (s.cache_dir / "smoke_tts.wav").write_bytes(wav_bytes(pcm, 8000))
        report("tts_rest", len(pcm) > 8000, f"{len(pcm) / 16000:.2f}s audio in {dt:.2f}s -> cache/smoke_tts.wav")
    except Exception as e:
        report("tts_rest", False, repr(e))

    # 2. STT REST
    if pcm:
        try:
            t0 = time.perf_counter()
            ev = await transcribe_rest(key, wav_bytes(pcm, 8000), language_code="hi-IN,en-IN")
            report("stt_rest", bool(ev.text), f"'{ev.text}' lang={ev.language} in {time.perf_counter() - t0:.2f}s")
        except Exception as e:
            report("stt_rest", False, repr(e))

    # 3. TTS stream
    try:
        t0 = time.perf_counter()
        first, total = None, 0
        async for chunk in tts_stream(key, "हाँ बेटा, <coughs> एक मिनट रुको।", voice="Lakshmi", language="hi-IN"):
            first = first or time.perf_counter() - t0
            total += len(chunk)
        report("tts_stream", total > 0, f"first chunk {first or 0:.2f}s, {total / 16000:.2f}s audio")
    except Exception as e:
        report("tts_stream", False, repr(e))

    # 4. STT stream (realtime pacing) + 5. concurrency (TTS while STT socket is open)
    if pcm:
        stream = PrismaStream(key, language_code="hi-IN,en-IN", sample_rate=8000)
        try:
            await stream.connect()
            got: list = []

            async def reader():
                async for ev in stream.events():
                    got.append(ev)
                    if ev.type in ("transcript", "closed"):
                        if ev.type == "transcript" and ev.text:
                            return

            rtask = asyncio.create_task(reader())
            silence = float_to_pcm16(np.zeros(8000, dtype=np.float32))
            t0 = time.perf_counter()
            send = asyncio.create_task(stream.send_pcm_realtime(pcm + silence))
            # concurrency check while the STT socket is busy
            try:
                await tts_rest(key, "ठीक है।", voice="Lakshmi", language="hi-IN")
                report("concurrency (TTS while STT open)", True, "allowed: use STT_MODE=stream")
            except Exception as e:
                report("concurrency (TTS while STT open)", False, f"{e!r} -> set STT_MODE=turn in .env")
            await send
            await stream.commit()
            try:
                await asyncio.wait_for(rtask, timeout=15)
            except asyncio.TimeoutError:
                pass
            tr = [e for e in got if e.type == "transcript" and e.text]
            info = (f"'{tr[0].text}' latency={tr[0].latency_ms}ms after {time.perf_counter() - t0:.1f}s"
                    if tr else f"events={[e.type for e in got]}")
            report("stt_stream", bool(tr), info)
        except Exception as e:
            report("stt_stream", False, repr(e))
        finally:
            await stream.close()

    # 6. LLM
    if args.llm:
        from voice_core.llm import LLM

        try:
            llm = LLM(s)
            t0 = time.perf_counter()
            first, text = None, ""
            async for d in llm.stream([{"role": "user", "content": "Ek line mein Hinglish mein bolo: beta, aap kaun?"}]):
                first = first or time.perf_counter() - t0
                text += d
            report(f"llm ({llm.provider}:{llm.model})", bool(text), f"first token {first or 0:.2f}s: {text.strip()[:80]}")
        except Exception as e:
            report("llm", False, repr(e))

    # 7. voice cloning (is it inside the key's TTS scope?)
    if args.clone:
        from voice_core.gnani import create_voice_embedding, tts_clone_rest

        try:
            sample = await tts_rest(
                key,
                "नमस्ते, मेरा नाम सुनीता है। मैं कानपुर में रहती हूँ और मुझे सुबह की चाय और पुराने गाने बहुत पसंद हैं। "
                "आज मौसम बहुत अच्छा है, इसलिए मैं पार्क में टहलने जाऊँगी।",
                voice="Kalpana", language="hi-IN", sample_rate=16000)
            emb = await create_voice_embedding(key, wav_bytes(sample, 16000))
            report("voice_clone_embedding", bool(emb.get("embedding")), f"shape={emb.get('shape')}")
            out = await tts_clone_rest(key, "ये मेरी आवाज़ है, अब तमिल में भी।", emb, language="hi-IN", sample_rate=16000)
            (s.cache_dir / "smoke_clone.wav").write_bytes(wav_bytes(out, 16000))
            report("voice_clone_tts", len(out) > 16000, f"{len(out) / 32000:.2f}s -> cache/smoke_clone.wav")
        except Exception as e:
            report("voice_clone", False, f"{e!r} (403 SCOPE_NOT_ALLOWED means cloning is not enabled for this key)")

    # 8. voices
    if args.voices:
        out = s.cache_dir / "voices"
        out.mkdir(parents=True, exist_ok=True)
        for v in V3_VOICES:
            try:
                a = await tts_rest(key, "अरे बेटा, <coughs> मेरा चश्मा कहाँ गया? रुको ज़रा।", voice=v,
                                   language="hi-IN", speed=0.9, sample_rate=16000)
                (out / f"{v}.wav").write_bytes(wav_bytes(a, 16000))
                print(f"  voice {v}: ok", flush=True)
            except Exception as e:
                print(f"  voice {v}: {e!r}", flush=True)
        print(f"Listen to the files in {out} and pick each persona's voice.")

    print("\nSUMMARY:", ", ".join(f"{n}={'ok' if ok else 'FAIL'}" for n, ok, _ in results))
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--llm", action="store_true")
    p.add_argument("--voices", action="store_true")
    p.add_argument("--clone", action="store_true", help="test Gnani voice cloning (needed by apni-awaaz)")
    sys.exit(asyncio.run(main(p.parse_args())))
