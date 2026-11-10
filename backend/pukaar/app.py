"""FastAPI app: caller WebSocket, control-room WebSocket, and REST for incidents, dispatch and callbacks.

Run:  bash run_backend.sh            (port 8766)
No keys / bad network:  FAKE=1 bash run_backend.sh   (scripted Tanglish caller, tone audio)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from voice_core.audio import wav_bytes
from voice_core.config import Settings, get_settings, repo_root
from voice_core.gnani import TtsCache, transcribe_rest, tts_rest
from voice_core.llm import LLM
from voice_core.session import VoiceAgentSession

from .agent import PukaarAgent, deliver_dispatch
from .allocate import live_status, load_teams, plan, recommend
from .assets import load_or_make_fillers, rain_noise
from .broadcast import BROADCAST_LANGS, make_broadcast
from .channels import cap_xml, relay_line, sms_intake
from .data import DATA, load_gazetteer, load_guidance
from .domain import Facts
from .fake_mode import FakeTriageLLM, ScriptedStt, tone_tts
from .hotspots import hotspots
from .interpreter import MAX_CLIP_BYTES, FakeInterpLLM, FakeTranscriber, Interpreter
from .sim import replay_surge, run_surge
from .sitrep import sitrep
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pukaar")
TO_CONTROL = {"incident", "turn", "language"}


class MessageIn(BaseModel):
    text: str


class SmsIn(BaseModel):
    text: str
    gps: tuple[float, float] | None = None  # [lat, lon]; anything else is a 422, not a crash in locate()


class CapItem(BaseModel):
    lang: str
    text: str


class CapIn(BaseModel):
    text_en: str
    items: list[CapItem]
    area: str = "Chennai"


class BroadcastIn(BaseModel):
    text_en: str
    langs: list[str] = BROADCAST_LANGS


class MissedCallIn(BaseModel):
    gps: tuple[float, float] | None = None


class SurgeIn(BaseModel):
    n: int = 20
    fresh: bool = False  # True = generate new callers with the LLM (and re-record); else replay the recording


class DispatchIn(BaseModel):
    team: str
    note: str = ""
    eta: str | None = None


def create_app(settings: Settings | None = None, *, session_factory=None, intel_llm=None, teams=None,
               interpreter_factory=None) -> FastAPI:
    settings = settings or get_settings()
    fake = os.environ.get("PUKAAR_FAKE") == "1"
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    store = Store(settings.cache_dir / ("pukaar_fake.db" if fake else "pukaar.db"))
    places, kb = load_gazetteer(), load_guidance()
    roster = tuple(load_teams() if teams is None else teams)
    intel_llm = intel_llm or (FakeTriageLLM() if fake else LLM(settings, purpose="intel"))
    tts_cache = TtsCache(settings.cache_dir)
    control: set[WebSocket] = set()
    live: dict[str, tuple[VoiceAgentSession, PukaarAgent]] = {}
    st = SimpleNamespace(fillers={}, rain=rain_noise(10.0, settings.sample_rate), ready=False, surge=None)

    def default_factory(store, send_json, send_audio, gps, call_id=None):
        if fake:
            llm = FakeTriageLLM()
            agent = PukaarAgent(llm=llm, intel_llm=llm, store=store, places=places, kb=kb, gps=gps, call_id=call_id)
            return VoiceAgentSession(agent, send_json=send_json, send_audio=send_audio, settings=settings,
                                     stt_factory=ScriptedStt, tts_fn=tone_tts, noise=st.rain), agent
        agent = PukaarAgent(llm=LLM(settings), intel_llm=LLM(settings, purpose="intel"), store=store,
                            places=places, kb=kb, gps=gps, call_id=call_id)
        return VoiceAgentSession(agent, send_json=send_json, send_audio=send_audio, settings=settings,
                                 filler_audio=st.fillers, noise=st.rain), agent

    factory = session_factory or default_factory
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async def warm():  # greeting + fillers rendered once (cached), so replies never start with silence
            st.fillers.update(await load_or_make_fillers(settings))
            st.ready = True
            log.info("assets ready: %d filler clips", len(st.fillers))

        task = None if (fake or session_factory) else asyncio.create_task(warm())
        st.ready = task is None
        yield
        if task and not task.done():
            task.cancel()

    app = FastAPI(title="Pukaar", lifespan=lifespan)
    app.state.store = store

    async def broadcast(m: dict) -> None:
        for ws in list(control):
            try:
                await ws.send_json(m)
            except Exception:
                control.discard(ws)

    async def say(sess: VoiceAgentSession, text: str) -> None:
        # ponytail: uses the session's private _speak_fixed; add a public say() to voice-core (in dadi-vs-scammers) if it changes
        if sess._speak_task and not sess._speak_task.done():
            sess._speak_task.cancel()
        sess._recent_agent_lines.append(text)
        sess._speak_task = asyncio.create_task(sess._speak_fixed(text))

    def get_or_404(x, what: str):
        if x is None:
            raise HTTPException(404, f"{what} not found")
        return x

    # ------------------------------------------------------------------ REST
    @app.get("/api/health")
    async def health():
        return {"gnani_key": bool(settings.gnani_api_key), "llm_key": bool(settings.groq_api_key or settings.evon_base_url),
                "llm_provider": settings.llm_provider, "intel_llm_provider": settings.intel_llm_provider,
                "stt_mode": settings.stt_mode, "fake": fake, "fillers_ready": st.ready}

    @app.get("/api/places")
    async def get_places():
        return [{"name": p.name, "aliases": p.aliases, "lat": p.lat, "lon": p.lon} for p in places]

    @app.get("/api/incidents")
    async def incidents(status: str | None = None):
        return [i.model_dump() for i in store.list_incidents(status)]

    @app.get("/api/incidents/{incident_id}")
    async def incident(incident_id: str):
        return get_or_404(store.get_incident(incident_id), "incident").model_dump()

    # ------------------------------------------------------------------ decision support (read-only; a human dispatches)
    @app.get("/api/teams")
    async def get_teams():
        return [t.__dict__ for t in live_status(roster, store.list_incidents())]

    @app.get("/api/incidents/{incident_id}/recommend")
    async def recommend_teams(incident_id: str):
        inc = get_or_404(store.get_incident(incident_id), "incident")
        teams = live_status(roster, store.list_incidents())
        return {"incident_id": inc.id, "recommendations": recommend(inc, teams, top=3),
                "teams_free": sum(t.status == "available" for t in teams)}

    @app.get("/api/plan")
    async def get_plan():
        incs = store.list_incidents()
        return plan(incs, live_status(roster, incs))

    @app.get("/api/sitrep")
    async def get_sitrep():
        return sitrep(store.list_incidents(), store.kpis()["calls"], time.time())

    @app.get("/api/hotspots")
    async def get_hotspots():
        return hotspots(store.list_incidents())

    @app.post("/api/incidents/{incident_id}/dispatch")
    async def dispatch(incident_id: str, body: DispatchIn):
        inc = get_or_404(store.dispatch(incident_id, body.team, body.note, body.eta), "incident")
        for cid in inc.call_ids:
            if cid in live:
                live[cid][1].eta = body.eta  # later replies may now mention the confirmed ETA
        await deliver_dispatch(store, inc, intel_llm,
                               {cid: (lambda t, s=live[cid][0]: say(s, t)) for cid in inc.call_ids if cid in live})
        await broadcast({"type": "incident", "incident": inc.model_dump()})
        await broadcast({"type": "kpis", **store.kpis()})
        return inc.model_dump()

    @app.post("/api/incidents/{incident_id}/message")
    async def message_callers(incident_id: str, body: MessageIn):
        """Dispatcher types English; every caller of the incident hears it in their own language (or by callback)."""
        inc = get_or_404(store.get_incident(incident_id), "incident")
        if not body.text.strip():
            raise HTTPException(400, "message is empty")
        sent = []
        for cid in inc.call_ids:
            lang = store.call_lang(cid)
            line = await relay_line(intel_llm, lang, body.text.strip())
            if cid in live:
                await say(live[cid][0], line)
            else:
                store.queue_callback(cid, line, lang)
            sent.append({"call_id": cid, "lang": lang, "text": line, "live": cid in live})
        return {"sent": sent}

    @app.post("/api/sms")
    async def sms(body: SmsIn):
        """SMS / WhatsApp intake: no voice call needed (weak network, speech-impaired, or a jammed line)."""
        if not body.text.strip():
            raise HTTPException(400, "message is empty")
        inc, reply = await sms_intake(body.text.strip()[:1000], tuple(body.gps) if body.gps else None, intel_llm, store,
                                      places, kb)
        await broadcast({"type": "incident", "incident": inc.model_dump()})
        await broadcast({"type": "kpis", **store.kpis()})
        return {"incident": inc.model_dump(), "reply": reply}

    @app.post("/api/broadcast/cap")
    async def broadcast_cap(body: CapIn):
        xml = cap_xml(body.text_en, [i.model_dump() for i in body.items if i.lang in BROADCAST_LANGS and i.text.strip()],
                      area=body.area, identifier=f"pukaar-{int(time.time())}-{uuid.uuid4().hex[:8]}")
        return Response(xml, media_type="application/xml",
                        headers={"Content-Disposition": "attachment; filename=pukaar-alert-cap.xml"})

    @app.post("/api/incidents/{incident_id}/resolve")
    async def resolve(incident_id: str):
        inc = get_or_404(store.resolve(incident_id), "incident")
        await broadcast({"type": "incident", "incident": inc.model_dump()})
        await broadcast({"type": "kpis", **store.kpis()})
        return inc.model_dump()

    @app.post("/api/missed-call")
    async def missed_call(body: MissedCallIn):
        """Missed-call jugaad: the caller spends nothing; the pin appears now and Pukaar calls back."""
        cid = store.create_call("ta-IN")
        loc = (body.gps[0], body.gps[1], "gps", 0.7) if body.gps else None
        inc = store.upsert_incident(cid, Facts(), loc, channel="missed_call")
        await broadcast({"type": "incident", "incident": inc.model_dump()})
        await broadcast({"type": "kpis", **store.kpis()})
        return {"call_id": cid, "incident": inc.model_dump()}

    @app.post("/api/surge")
    async def surge(body: SurgeIn):
        """Flood-night replay: synthetic text callers through the real triage (LLM only, no Gnani credits)."""
        if st.surge and not st.surge.done():
            raise HTTPException(409, "a surge is already running")
        rec = settings.cache_dir / ("surge_fake.json" if fake else "surge_recording.json")
        demo = DATA / "surge_demo.json"  # committed recording, so a fresh clone can replay without tokens
        # fake mode always replays the committed recording: the fake LLM only knows the scripted call's 4 facts
        src = demo if fake else rec if rec.exists() else demo
        if src.exists() and not body.fresh:  # replay: no LLM calls, so live calls keep the Groq token budget
            rows = json.loads(src.read_text(encoding="utf-8"))[: max(1, min(40, body.n))]
            st.surge = asyncio.create_task(replay_surge(rows, store, places, broadcast))
            return {"started": len(rows), "mode": "replay"}
        n = max(1, min(40, body.n))
        st.surge = asyncio.create_task(run_surge(n, intel_llm, store, places, broadcast, random.Random(), record=rec))
        return {"started": n, "mode": "generate"}

    @app.get("/api/drill")
    async def drill():
        f = DATA / "drill_results.json"  # written by scripts/run_drill.py
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"rows": [], "summary": None}

    @app.post("/api/broadcast")
    async def broadcast_alert(body: BroadcastIn):
        """District officer's alert, spoken in every chosen language (Timbre MP3, cached by text)."""
        if not body.text_en.strip():
            raise HTTPException(400, "alert text is empty")
        langs = [l for l in dict.fromkeys(body.langs) if l in BROADCAST_LANGS]

        async def tts(text: str, lang: str) -> str:
            kw = dict(voice=PukaarAgent.voice, language=lang, speed=PukaarAgent.speed, sample_rate=24000, container="mp3")
            key = tts_cache.key(text, **kw)
            if tts_cache.get(key) is None:
                if fake:
                    pcm = b"".join([c async for c in tone_tts(None, text, sample_rate=8000)])
                    tts_cache.put(key, wav_bytes(pcm, 8000))
                else:
                    await tts_cache.get_or_make(settings.gnani_api_key, text, **kw)
            return key

        items = await make_broadcast(body.text_en.strip(), langs, intel_llm, tts, places)
        return [{**{k: v for k, v in i.items() if k != "audio"}, "audio_url": f"/api/broadcast/audio/{i['audio']}"} for i in items]

    @app.get("/api/broadcast/audio/{key}")
    async def broadcast_audio(key: str):
        data = tts_cache.get(key) if re.fullmatch(r"[0-9a-f]{40}", key) else None
        if data is None:
            raise HTTPException(404, "audio not found")
        return Response(data, media_type="audio/wav" if data[:4] == b"RIFF" else "audio/mpeg")

    @app.get("/api/kpis")
    async def kpis():
        return store.kpis()

    @app.get("/api/calls/{call_id}")
    async def call(call_id: str):
        return get_or_404(store.get_call(call_id), "call")

    @app.get("/api/calls/{call_id}/callbacks")
    async def callbacks(call_id: str):
        get_or_404(store.get_call(call_id), "call")
        return store.pending_callbacks(call_id)

    @app.get("/api/calls/{call_id}/callbacks/{cb_id}/audio")
    async def callback_audio(call_id: str, cb_id: str):
        cb = get_or_404(next((c for c in store.pending_callbacks(call_id) if c["id"] == cb_id), None), "callback")
        kw = dict(voice=PukaarAgent.voice, language=cb["lang"], speed=PukaarAgent.speed, sample_rate=settings.sample_rate)
        if fake:
            pcm = b"".join([c async for c in tone_tts(None, cb["text"], sample_rate=settings.sample_rate)])
        else:
            pcm = await tts_cache.get_or_make(settings.gnani_api_key, cb["text"], **kw)
        return Response(wav_bytes(pcm, settings.sample_rate), media_type="audio/wav")

    @app.get("/api/guidance")
    async def guidance():
        return [g.__dict__ for g in kb]

    # ------------------------------------------------------------------ control room
    @app.websocket("/ws/control")
    async def ws_control(ws: WebSocket):
        await ws.accept()
        await ws.send_json({"type": "snapshot", "incidents": [i.model_dump() for i in store.list_incidents()],
                            "kpis": store.kpis(), "live_calls": list(live)})
        control.add(ws)
        try:
            while True:
                await ws.receive_text()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            control.discard(ws)

    # ------------------------------------------------------------------ caller
    @app.websocket("/ws/call")
    async def ws_call(ws: WebSocket):
        await ws.accept()
        lock = asyncio.Lock()
        alive = {"v": True}
        holder: dict = {}

        async def send_json(m: dict):
            if alive["v"]:
                try:
                    async with lock:
                        await ws.send_json(m)
                except Exception:
                    alive["v"] = False
            if m.get("type") in TO_CONTROL and "agent" in holder:
                await broadcast({**m, "call_id": holder["agent"].call_id})
                if m["type"] == "incident":
                    await broadcast({"type": "kpis", **store.kpis()})

        async def send_audio(b: bytes):
            if alive["v"]:
                try:
                    async with lock:
                        await ws.send_bytes(b)
                except Exception:
                    alive["v"] = False

        try:
            first = await ws.receive_json()
        except Exception:
            return
        if first.get("type") != "start":
            await ws.close(code=1008)
            return
        gps = tuple(first["gps"]) if first.get("gps") else None
        callback_for = first.get("callback_for")
        if callback_for and (store.get_call(callback_for) is None or callback_for in live):
            callback_for = None
        sess, agent = factory(store, send_json, send_audio, gps, callback_for)
        holder["agent"] = agent
        live[agent.call_id] = (sess, agent)
        await broadcast({"type": "call_started", "call_id": agent.call_id, "gps": gps})
        await sess.start()
        if first.get("noise_snr_db") is not None:
            await sess.set_noise(float(first["noise_snr_db"]))
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes"):
                    await sess.on_audio(msg["bytes"])
                elif msg.get("text"):
                    d = json.loads(msg["text"])
                    if d.get("type") == "hangup":
                        break
                    if d.get("type") == "set_noise":
                        snr = d.get("snr_db")
                        await sess.set_noise(None if snr is None else float(snr))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            live.pop(agent.call_id, None)
            res = await sess.hangup()
            await send_json({"type": "call_ended", "call_id": agent.call_id, "seconds": res["session_seconds"]})
            await broadcast({"type": "call_ended", "call_id": agent.call_id})
            await broadcast({"type": "kpis", **store.kpis()})
            alive["v"] = False
            try:
                await ws.close()
            except Exception:
                pass


    # ------------------------------------------------------------------ rescuer <-> caller interpreter
    async def interp_speak(text: str, lang: str, voice: str) -> tuple[str, float]:
        """Timbre WAV for one interpreted line (cached by text, voice and language) -> (audio url, seconds)."""
        hz = 8000 if fake else 24000
        kw = dict(voice=voice, language=lang, speed=1.0, sample_rate=hz)
        key = tts_cache.key(text, wav=True, **kw)
        data = tts_cache.get(key)
        if data is None:
            if fake:
                pcm = b"".join([c async for c in tone_tts(None, text, sample_rate=hz)])
            else:
                pcm = await tts_rest(settings.gnani_api_key, text, **kw)
            data = wav_bytes(pcm, hz)
            tts_cache.put(key, data)
        return f"/api/interpret/audio/{key}", (len(data) - 44) / (2 * hz)

    async def interp_transcribe(wav: bytes, lang: str, role: str) -> tuple[str, float | None]:
        ev = await transcribe_rest(settings.gnani_api_key, wav, language_code=lang)
        return ev.text, ev.latency_ms

    def default_interpreter(rescuer_lang: str, caller_lang: str) -> Interpreter:
        if fake:
            return Interpreter(transcribe=FakeTranscriber(), llm=FakeInterpLLM(), speak=interp_speak,
                               rescuer_lang=rescuer_lang, caller_lang=caller_lang)
        return Interpreter(transcribe=interp_transcribe, llm=LLM(settings), speak=interp_speak,
                           rescuer_lang=rescuer_lang, caller_lang=caller_lang)

    make_interpreter = interpreter_factory or default_interpreter

    @app.get("/api/interpret/audio/{key}")
    async def interpret_audio(key: str):
        data = tts_cache.get(key) if re.fullmatch(r"[0-9a-f]{40}", key) else None
        if data is None or data[:4] != b"RIFF":
            raise HTTPException(404, "audio not found")
        return Response(data, media_type="audio/wav")

    @app.websocket("/ws/interpret")
    async def ws_interpret(ws: WebSocket):
        """Protocol (docs/API.md): start -> talk/<PCM16 frames>/done per turn -> turn messages with both captions."""
        await ws.accept()
        lock = asyncio.Lock()

        async def send(m: dict) -> None:
            try:
                async with lock:
                    await ws.send_json(m)
            except Exception:
                pass

        try:
            first = await ws.receive_json()
        except Exception:
            return
        try:
            if first.get("type") != "start":
                raise ValueError("first message must be start")
            hz = int(first.get("sample_rate") or 16000)
            if hz not in (8000, 16000):
                raise ValueError("sample_rate must be 8000 or 16000")
            interp = make_interpreter(first.get("rescuer_lang") or "hi-IN", first.get("caller_lang") or "ta-IN")
        except (ValueError, TypeError) as e:
            await send({"type": "error", "error": str(e)})
            await ws.close(code=1008)
            return
        await send({**interp.state(), "type": "ready", "machine_interpretation": True})
        buf = bytearray()
        work: set[asyncio.Task] = set()

        async def run_turn(role: str, wav: bytes) -> None:
            await send({"type": "interpreting", "role": role})
            try:
                await send(await interp.turn(role, wav))
            except Exception as e:  # Prisma/Timbre down: say so, never leave the floor locked
                log.warning("interpreter turn failed: %s", e)
                interp.release(role)
                await send({"type": "error", "role": role, "error": "Interpretation failed for this turn. Please try again."})
            await send({"type": "floor_free"})

        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes"):
                    if interp.speaking and not any(not t.done() for t in work) and len(buf) < MAX_CLIP_BYTES:
                        buf.extend(msg["bytes"][: MAX_CLIP_BYTES - len(buf)])
                    continue
                if not msg.get("text"):
                    continue
                try:
                    d = json.loads(msg["text"])
                    kind, role = d.get("type"), d.get("role")
                    if kind == "set_lang":
                        interp.set_lang(role, d.get("lang"))
                        await send(interp.state())
                    elif kind == "talk":
                        if any(not t.done() for t in work):  # the last turn is still being interpreted
                            await send({"type": "busy", "role": role, "speaking": interp.speaking})
                            continue
                        res = interp.claim(role)
                        if res["type"] == "floor":
                            buf.clear()
                        await send(res)
                    elif kind == "done":
                        if interp.speaking != role:
                            continue
                        clip, too_short = bytes(buf), len(buf) < hz * 2 // 4  # under 0.25 s: a mis-tap
                        buf.clear()
                        if too_short:
                            interp.release(role)
                            await send({"type": "unheard", "role": role, "original": "", "reason": "too short"})
                            await send({"type": "floor_free"})
                            continue
                        t = asyncio.create_task(run_turn(role, wav_bytes(clip, hz)))
                        work.add(t)
                        t.add_done_callback(work.discard)
                    elif kind == "cancel":
                        if not any(not t.done() for t in work):
                            interp.release(role)
                            buf.clear()
                            await send({"type": "floor_free"})
                    elif kind == "hangup":
                        break
                except (ValueError, TypeError, json.JSONDecodeError) as e:
                    await send({"type": "error", "error": str(e)})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            for t in list(work):
                t.cancel()
            try:
                await ws.close()
            except Exception:
                pass

    dist = repo_root() / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")
    return app
