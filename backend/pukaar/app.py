"""FastAPI app: caller WebSocket, control-room WebSocket, and REST for incidents, dispatch and callbacks.

Run:  bash run_backend.sh            (port 8766)
No keys / bad network:  FAKE=1 bash run_backend.sh   (scripted Tanglish caller, tone audio)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from voice_core.config import Settings, get_settings, repo_root
from voice_core.llm import LLM
from voice_core.session import VoiceAgentSession

from .agent import PukaarAgent, deliver_dispatch
from .data import load_gazetteer, load_guidance
from .fake_mode import FakeTriageLLM, ScriptedStt, tone_tts
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pukaar")
TO_CONTROL = {"incident", "turn", "language"}


class DispatchIn(BaseModel):
    team: str
    note: str = ""
    eta: str | None = None


def create_app(settings: Settings | None = None, *, session_factory=None, intel_llm=None) -> FastAPI:
    settings = settings or get_settings()
    fake = os.environ.get("PUKAAR_FAKE") == "1"
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    store = Store(settings.cache_dir / ("pukaar_fake.db" if fake else "pukaar.db"))
    places, kb = load_gazetteer(), load_guidance()
    intel_llm = intel_llm or (FakeTriageLLM() if fake else LLM(settings, purpose="intel"))
    control: set[WebSocket] = set()
    live: dict[str, tuple[VoiceAgentSession, PukaarAgent]] = {}

    def default_factory(store, send_json, send_audio, gps):
        if fake:
            llm = FakeTriageLLM()
            agent = PukaarAgent(llm=llm, intel_llm=llm, store=store, places=places, kb=kb, gps=gps)
            return VoiceAgentSession(agent, send_json=send_json, send_audio=send_audio, settings=settings,
                                     stt_factory=ScriptedStt, tts_fn=tone_tts), agent
        agent = PukaarAgent(llm=LLM(settings), intel_llm=LLM(settings, purpose="intel"), store=store,
                            places=places, kb=kb, gps=gps)
        return VoiceAgentSession(agent, send_json=send_json, send_audio=send_audio, settings=settings), agent

    factory = session_factory or default_factory
    app = FastAPI(title="Pukaar")

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
                "stt_mode": settings.stt_mode, "fake": fake}

    @app.get("/api/places")
    async def get_places():
        return [{"name": p.name, "aliases": p.aliases, "lat": p.lat, "lon": p.lon} for p in places]

    @app.get("/api/incidents")
    async def incidents(status: str | None = None):
        return [i.model_dump() for i in store.list_incidents(status)]

    @app.get("/api/incidents/{incident_id}")
    async def incident(incident_id: str):
        return get_or_404(store.get_incident(incident_id), "incident").model_dump()

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

    @app.post("/api/incidents/{incident_id}/resolve")
    async def resolve(incident_id: str):
        inc = get_or_404(store.resolve(incident_id), "incident")
        await broadcast({"type": "incident", "incident": inc.model_dump()})
        await broadcast({"type": "kpis", **store.kpis()})
        return inc.model_dump()

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
        sess, agent = factory(store, send_json, send_audio, gps)
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

    dist = repo_root() / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")
    return app
