"""Refresh the static Vercel demo from a recorded run: GET snapshots, WebSocket timelines and audio.

    uv run python scripts/snapshot_demo.py [--call CALL_ID] [--caller-wav caller.wav] [--cap cap.xml]

Reads cache/pukaar.db and cache/tts through the real FastAPI app, in-process, with every API key blanked, a
dummy LLM and no voice sessions: it cannot reach Gnani or Groq. Writes frontend/demo/ (served as /demo/... by the
demo build only; see docs/DEPLOY-VERCEL.md).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import sys
import wave
from pathlib import Path

os.environ["PUKAAR_FAKE"] = "0"  # the real database, never the fake-mode one

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from voice_core.config import get_settings, repo_root  # noqa: E402
from voice_core.gnani import TtsCache  # noqa: E402

from pukaar.agent import GREETING, PukaarAgent  # noqa: E402
from pukaar.app import create_app  # noqa: E402
from pukaar.domain import Facts, score  # noqa: E402

ROOT = repo_root()
OUT = ROOT / "frontend" / "demo"  # copied to dist/demo by vite.config.js in demo mode only
SURGE_GAP_S = 0.9  # surge callers start ~1 s apart in the recording


class NoLLM:
    """Snapshots never call an LLM; any attempt is a bug."""

    async def complete(self, *a, **k):
        raise RuntimeError("snapshot_demo must not call an LLM")


def no_sessions(*a, **k):
    raise RuntimeError("snapshot_demo must not open a voice session")


def write(rel: str, data) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def staged(inc: dict, stage: int, call_id: str) -> dict:
    """The call's incident as it stood after `stage` caller answers: final facts masked, same rule table."""
    keep = [{"hazard", "locality", "landmark", "lat", "lon", "caller_language"},
            {"people_count", "on_roof", "water_level", "trapped"},
            {"vulnerable", "medical_needs", "injuries", "needs"}]
    allowed = set().union(*keep[: stage + 1])
    f = Facts(**{k: v for k, v in inc["facts"].items() if k in allowed})
    return {**inc, "facts": f.model_dump(), "severity": score(f).model_dump(), "call_ids": [call_id],
            "status": "new", "dispatch": None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--call", help="voice call to replay (default: the first call with turns)")
    ap.add_argument("--caller-wav", help="the synthetic caller's audio as fed to the mic (optional)")
    ap.add_argument("--caller-offset", type=float, default=0.9, help="seconds of silence before the caller audio")
    ap.add_argument("--cap", help="a CAP XML exported during the run (optional)")
    args = ap.parse_args()

    settings = dataclasses.replace(get_settings(), gnani_api_key="", groq_api_key="", evon_base_url="",
                                   evon_api_key="")
    app = create_app(settings, session_factory=no_sessions, intel_llm=NoLLM())
    store = app.state.store
    OUT.mkdir(parents=True, exist_ok=True)

    with TestClient(app) as c:
        get = lambda p: c.get(p).raise_for_status().json()  # noqa: E731
        for name in ("places", "guidance", "incidents", "kpis", "drill"):
            write(f"api/{name}.json", get(f"/api/{name}"))
        incidents = get("/api/incidents")
        kpis = get("/api/kpis")
        for inc in incidents:
            write(f"api/incidents/{inc['id']}.json", inc)
        calls = [dict(r) for r in store.db.execute("SELECT * FROM calls ORDER BY started_at")]
        for call in calls:
            write(f"api/calls/{call['id']}.json", get(f"/api/calls/{call['id']}"))
            write(f"api/calls/{call['id']}/callbacks.json", get(f"/api/calls/{call['id']}/callbacks"))
    # the recorded health of the live run (this process has no keys on purpose)
    write("api/health.json", {"gnani_key": True, "llm_key": True, "llm_provider": settings.llm_provider,
                              "intel_llm_provider": settings.intel_llm_provider, "stt_mode": settings.stt_mode,
                              "fake": False, "fillers_ready": True, "demo": True})

    by_id = {i["id"]: i for i in incidents}
    first = {}  # incident id -> first call time
    for call in calls:
        first.setdefault(call["incident_id"], call["started_at"])

    # ---------------------------------------------------------------- control room: snapshot + surge replay
    turns = {call["id"]: store.get_call(call["id"])["turns"] for call in calls}
    surge = [c for c in calls if len(turns[c["id"]]) == 1 and turns[c["id"]][0]["speaker"] == "caller"]
    t0 = surge[0]["started_at"] if surge else None
    before_ids = {c["id"] for c in calls if t0 is None or c["started_at"] < t0}
    before = [{**i, "call_ids": [x for x in i["call_ids"] if x in before_ids]} for i in incidents
              if t0 is None or first[i["id"]] < t0]
    open_ = [i for i in before if i["status"] != "resolved"]
    replied = [c for c in calls if c["id"] in before_ids and c["replies"]]
    kpis_before = {"calls": len(before_ids),
                   "avg_answer_s": round(sum(c["reply_s"] for c in replied) / sum(c["replies"] for c in replied), 2)
                   if replied else None,
                   "critical_open": sum(i["severity"]["level"] == "critical" for i in open_),
                   "people_affected": sum(i["facts"]["people_count"] or 1 for i in open_)}
    events, seen = [], set()
    for n, call in enumerate(surge):
        t = round(call["started_at"] - t0, 2)
        if call["incident_id"] not in seen:
            seen.add(call["incident_id"])
            events.append({"t": t, "msg": {"type": "incident", "incident": by_id[call["incident_id"]]}})
        events.append({"t": t, "msg": {"type": "kpis", **kpis_before, "calls": len(before_ids) + n + 1}})
    if surge:
        events.append({"t": events[-1]["t"] + SURGE_GAP_S, "msg": {"type": "kpis", **kpis}})
    write("control.json", {"snapshot": {"type": "snapshot", "incidents": incidents, "kpis": kpis, "live_calls": []},
                           "surge": {"before": {"type": "snapshot", "incidents": before, "kpis": kpis_before,
                                                "live_calls": []}, "events": events}})

    # ---------------------------------------------------------------- caller phone: one recorded voice call
    voice = [c for c in calls if len(turns[c["id"]]) > 3]
    call = next(c for c in voice if c["id"] == args.call) if args.call else voice[0]
    cid, tt = call["id"], turns[call["id"]]
    inc = by_id[call["incident_id"]]
    ev = [{"t": 0.0, "msg": {"type": "session_started", "call_id": cid, "started_at": call["started_at"]}},
          {"t": 0.3, "msg": {"type": "status", "stt": "connected"}}]
    caller_n = 0
    stage = -1
    for k, turn in enumerate(tt):
        t = float(turn["t"])
        msg = {"type": "turn", "speaker": turn["speaker"], "text": turn["text"], "t": t}
        if turn["speaker"] == "caller":
            msg.update(lang=turn.get("lang"), latency_ms=turn.get("latency_ms"))
        ev.append({"t": t, "msg": msg})
        if turn["speaker"] == "pukaar":
            nxt = next((float(x["t"]) for x in tt[k + 1:] if x["speaker"] == "caller"), t + 12)
            speak = min(t + max(3.0, 0.075 * len(turn["text"])), nxt - 0.5)
            ev.append({"t": t, "msg": {"type": "agent_speaking", "on": True}})
            ev.append({"t": round(speak, 2), "msg": {"type": "agent_speaking", "on": False}})
        else:
            caller_n += 1
            if caller_n == 1 and turn.get("lang"):
                ev.append({"t": t, "msg": {"type": "language", "call_id": cid, "language": turn["lang"],
                                           "language_name": "Tamil" if turn["lang"] == "ta-IN" else turn["lang"]}})
        # facts arrive after each caller answer (the next Pukaar reply follows them): stage = answers so far
        if turn["speaker"] == "pukaar" and k > 0:
            stage += 1
            if stage <= 2:
                ev.append({"t": round(t - 1.0, 2), "msg": {"type": "incident", "call_id": cid,
                                                 "incident": staged(inc, stage, cid)}})
    end = round(float(tt[-1]["t"]) + 6.0, 2)
    ev.sort(key=lambda e: e["t"])
    write("call.json", {"call_id": cid, "seconds": end, "final_incident": inc, "events": ev,
                        "greeting_audio": "/demo/audio/greeting.pcm", "caller_audio": "/demo/audio/caller.wav"})

    # ---------------------------------------------------------------- audio
    audio = OUT / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    cache = TtsCache(settings.cache_dir)
    g = cache.get(cache.key(GREETING, voice=PukaarAgent.voice, language="ta-IN", speed=PukaarAgent.speed,
                            sample_rate=settings.sample_rate))
    if g:
        (audio / "greeting.pcm").write_bytes(g)  # raw PCM16 at 8 kHz, played through the app's own PCM player
    if args.caller_wav:
        with wave.open(args.caller_wav, "rb") as w:
            sr, pcm = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        pcm = pcm[: int(sr * end)]
        idx = np.arange(0, len(pcm), sr / 8000).astype(int)  # to 8 kHz phone audio
        pcm8 = np.concatenate([np.zeros(int(8000 * args.caller_offset), np.int16), pcm[idx]])
        with wave.open(str(audio / "caller.wav"), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(8000), w.writeframes(pcm8.tobytes())

    # ---------------------------------------------------------------- broadcast + CAP (from the exported CAP)
    cap_src = Path(args.cap) if args.cap else OUT / "cap.xml"
    if args.cap:
        shutil.copyfile(cap_src, OUT / "cap.xml")
    if cap_src.exists():
        xml = cap_src.read_text(encoding="utf-8")
        names = {"ta": "Tamil", "hi": "Hindi", "te": "Telugu", "en": "English", "ml": "Malayalam", "kn": "Kannada",
                 "bn": "Bengali"}
        items = []
        for lang, text in re.findall(r"<language>([^<]+)</language>.*?<description>([^<]*)</description>", xml, re.S):
            key = cache.key(text, voice=PukaarAgent.voice, language=lang, speed=PukaarAgent.speed, sample_rate=24000,
                            container="mp3")
            item = {"lang": lang, "language": names.get(lang.split("-")[0], lang), "text": text, "audio_url": None}
            if cache.get(key):
                shutil.copyfile(cache.path(key), audio / f"{key}.mp3")
                item["audio_url"] = f"/demo/audio/{key}.mp3"
            items.append(item)
        write("broadcast.json", items)

    # ---------------------------------------------------------------- SMS: the recorded replies
    sms = []
    for c in calls:
        tt_ = turns[c["id"]]
        if len(tt_) == 2 and tt_[0]["speaker"] == "caller" and tt_[1]["speaker"] == "pukaar":
            sms.append({"text": tt_[0]["text"], "reply": tt_[1]["text"], "incident": by_id[c["incident_id"]]})
    write("sms.json", sms)
    print(f"demo snapshot: {len(incidents)} incidents, {len(calls)} calls, call replay {cid} ({end} s), "
          f"{len(events)} surge events, {len(sms)} SMS -> {OUT.relative_to(ROOT)}")
    import snapshot_decision  # same folder; recommender, plan, SitRep and hotspots from the incidents just written
    snapshot_decision.main()


if __name__ == "__main__":
    sys.exit(main())
