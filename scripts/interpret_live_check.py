"""Live check of the rescuer <-> caller interpreter (uses the Gnani key and the LLM key in .env).

Synthesises a short exchange with Timbre (a synthetic rescuer speaking Hindi, a synthetic caller speaking Tamil),
drives it through /ws/interpret at real-time pace (100 ms PCM frames, 16 kHz) and saves the timeline, the input clips
and the interpreted Timbre clips to frontend/demo/interpret/ for the static demo's "Play a recorded interpretation".
Every Gnani request is sequential (one at a time). Run: uv run python scripts/interpret_live_check.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from voice_core.audio import wav_bytes  # noqa: E402
from voice_core.config import get_settings  # noqa: E402
from voice_core.gnani import tts_rest  # noqa: E402

from pukaar.app import create_app  # noqa: E402

OUT = ROOT / "frontend" / "demo" / "interpret"
HZ = 16000
EXCHANGE = [  # (role, synthetic speaker voice, language, words)
    ("rescuer", "Shubham", "hi-IN", "हम नाव लेकर आ रहे हैं। आपके घर के पास कौन सी बड़ी इमारत है?"),
    ("caller", "Kalpana", "ta-IN", "வேளச்சேரி பஸ் டிப்போ பக்கத்துல இருக்கோம். மூணாவது மாடில நாங்க 4 பேர் இருக்கோம்."),
]


FAKE = "--fake" in sys.argv  # dry run with no keys: tones in, fake mode inside, writes to a scratch folder


async def synth(text: str, voice: str, lang: str) -> bytes:
    if FAKE:
        return bytes(HZ * 4)
    for attempt in range(3):
        try:
            return await tts_rest(get_settings().gnani_api_key, text, voice=voice, language=lang, sample_rate=HZ)
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(1.5)
    raise RuntimeError("unreachable")


def until(ws, *types):
    while True:
        m = ws.receive_json()
        if m.get("type") in types:
            return m


def main() -> None:
    global OUT
    sys.stdout.reconfigure(encoding="utf-8")  # Tamil/Hindi captions on a Windows console
    if FAKE:
        import os
        import tempfile
        os.environ["PUKAAR_FAKE"] = "1"
        OUT = Path(tempfile.mkdtemp(prefix="interp-dry-"))
    OUT.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, (role, voice, lang, text) in enumerate(EXCHANGE, 1):
        pcm = asyncio.run(synth(text, voice, lang))
        (OUT / f"in-{i}-{role}.wav").write_bytes(wav_bytes(pcm, HZ))
        clips.append(pcm)
        print(f"synthesised {role} ({lang}, {voice}): {len(pcm) / 2 / HZ:.1f} s")

    settings = get_settings()
    # session_factory set: skips the helpline's filler warm-up, so this script makes only its own Gnani requests
    app = create_app(settings, session_factory=lambda *a, **k: None)
    timeline = {"recorded": datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M IST"),
                "llm": None, "turns": []}
    with TestClient(app) as c:
        timeline["llm"] = c.get("/api/health").json().get("llm_provider")
        with c.websocket_connect("/ws/interpret") as ws:
            ws.send_json({"type": "start", "rescuer_lang": "hi-IN", "caller_lang": "ta-IN", "sample_rate": HZ})
            print(until(ws, "ready")["langs"])
            for i, ((role, _, _, text), pcm) in enumerate(zip(EXCHANGE, clips), 1):
                ws.send_json({"type": "talk", "role": role})
                assert until(ws, "floor", "busy")["type"] == "floor"
                step = HZ * 2 // 10
                for k in range(0, len(pcm), step):  # real-time pace, like a held push-to-talk button
                    ws.send_bytes(pcm[k:k + step])
                    time.sleep(0.1)
                released = time.monotonic()
                ws.send_json({"type": "done", "role": role})
                m = until(ws, "turn", "unheard", "error")
                after_release = round((time.monotonic() - released) * 1000)
                if m["type"] != "turn":
                    raise SystemExit(f"turn {i} failed: {m}")
                audio = c.get(m["audio_url"]).content
                (OUT / f"out-{i}-{role}.wav").write_bytes(audio)
                until(ws, "floor_free")
                m = {**m, "spoken_text": text, "release_to_audio_ms": after_release,
                     "input_audio": f"/demo/interpret/in-{i}-{role}.wav", "audio_url": f"/demo/interpret/out-{i}-{role}.wav",
                     "input_s": round(len(pcm) / 2 / HZ, 2)}
                timeline["turns"].append(m)
                print(json.dumps({k: m[k] for k in ("role", "original", "translation", "note", "prisma_ms", "stt_ms",
                                                    "translate_ms", "tts_ms", "total_ms", "release_to_audio_ms")},
                                 ensure_ascii=False))
            ws.send_json({"type": "hangup"})
    (OUT / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", OUT)


if __name__ == "__main__":
    main()
