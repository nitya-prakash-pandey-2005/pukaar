"""PukaarAgent: the voice-core Agent for the disaster helpline, plus dispatch callback delivery."""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Awaitable, Callable

from voice_core.turns import split_sentences
from voice_core.types import Turn

from .data import Guidance, Place
from .domain import KEYTERMS, Facts, Incident, locate, next_slot, resolve_locality
from .guard import fallback, guard_reply
from .store import Store
from .triage import LANG_NAMES, build_reply_messages, extract_facts, pick_guidance

STT_HINT = "ta-IN,hi-IN,en-IN,te-IN"
TTS_LANGS = {"hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "bn-IN", "gu-IN"}
GREETING = "பதட்டப்படாதீங்க, நான் உதவறேன். Pukaar helpline. Aap kahan hain?"
CALLBACK_GREETING = "வணக்கம், Pukaar helpline. நீங்க missed call கொடுத்தீங்க, நாங்க திரும்ப கூப்பிடறோம். நீங்க எங்க இருக்கீங்க?"
FILLERS = {
    "ta": ["சரி, கேக்கறேன்.", "ம்ம், சொல்லுங்க."],
    "hi": ["हाँ, मैं सुन रही हूँ।", "जी, बताइए।"],
    "te": ["సరే, వింటున్నాను."],
    "en": ["Okay, I'm listening.", "Yes, go on."],
}


class PukaarAgent:
    user_label = "caller"
    agent_label = "pukaar"
    voice = "Chetana"
    speed = 0.95
    stt_language_code = STT_HINT
    keyterms = KEYTERMS

    def __init__(self, *, llm, intel_llm, store: Store, places: list[Place], kb: list[Guidance],
                 gps: tuple[float, float] | None = None, call_id: str | None = None):
        self.llm, self.intel_llm, self.store = llm, intel_llm, store
        self.places, self.kb, self.gps = places, kb, gps
        self.tts_language = "ta-IN"
        self.callback = call_id is not None  # calling back a missed call: continue that call and its incident
        self.call_id = call_id or store.create_call(self.tts_language)
        self.facts = Facts()
        self.asked: set[str] = set()
        self.given: set[str] = set()
        self.eta: str | None = None
        self._x_len = -1
        self._x_task: asyncio.Task | None = None

    def session_info(self) -> dict:
        return {"call_id": self.call_id, "gps": self.gps}

    def greeting(self) -> str:
        return CALLBACK_GREETING if self.callback else GREETING

    def filler_texts(self) -> list[str]:
        return FILLERS.get(self.tts_language.split("-")[0], FILLERS["en"])

    def on_language(self, code: str | None) -> dict | None:
        if code not in TTS_LANGS:
            return None
        self.tts_language = code
        self.store.set_lang(self.call_id, code)
        return {"type": "language", "call_id": self.call_id, "language": code,
                "language_name": LANG_NAMES.get(code.split("-")[0])}

    async def _facts_for(self, history: list[Turn]) -> Facts:
        """One extraction per caller turn, shared by reply_sentences and on_user_turn (they run concurrently)."""
        if self._x_len != len(history):
            self._x_len = len(history)
            self._x_task = asyncio.ensure_future(extract_facts(self.intel_llm, history, self.facts))
        # shield: a barge-in cancels the reply task, which must not cancel the shared extraction
        self.facts = await asyncio.shield(self._x_task)
        return self.facts

    async def reply_sentences(self, history: list[Turn]) -> AsyncIterator[str]:
        t0 = time.monotonic()
        f = await self._facts_for(history)
        slot = next_slot(f, self.asked)
        # GEN-01 says the control room can see the caller on the map: only true once they are located
        located = locate(f, self.places, self.gps) is not None
        cands = pick_guidance(f, self.kb, self.given if located else self.given | {"GEN-01"})
        msgs = build_reply_messages(f, slot, cands, self.tts_language, self.eta, history)
        try:
            # not streamed: the guard must see the whole reply before anything is spoken
            raw = await self.llm.complete(msgs, temperature=0.4, max_tokens=120)
        except Exception:
            raw = ""
        text, ids = guard_reply(raw, {g.id for g in cands}, self.eta, self.tts_language)
        spoken = bool(text) and text != fallback(self.tts_language)  # the LLM's own reply survived the guard
        if not spoken:  # LLM error, empty, only a tag, or blocked: the safe line, which asks and gives nothing
            text, ids = fallback(self.tts_language), []
        if slot and spoken:
            self.asked.add(slot)
        if ids:
            self.given.update(ids)
            self.store.add_guidance(self.call_id, ids)
        self.store.add_reply_latency(self.call_id, time.monotonic() - t0)
        sentences, rest = split_sentences(text)
        for s in sentences + ([rest] if rest.strip() else []):
            yield s.strip()

    async def on_user_turn(self, history: list[Turn]) -> dict | None:
        said = [t.text for t in history if t.speaker == self.user_label]
        f = resolve_locality(await self._facts_for(history), said, self.places, self.gps)
        inc = self.store.upsert_incident(self.call_id, f, locate(f, self.places, self.gps))
        return {"type": "incident", "call_id": self.call_id, "incident": inc.model_dump()}

    async def record(self, turn: Turn) -> None:
        self.store.add_turn(self.call_id, turn)

    def end(self, seconds: float) -> None:
        self.store.end_call(self.call_id, seconds)


async def dispatch_line(llm, lang: str, team: str, eta: str | None) -> str:
    """The dispatcher's message in the caller's language; never adds a time the dispatcher did not enter."""
    base = f"A rescue team ({team}) is on the way." + (f" Expected in {eta}." if eta else "") + \
        " Stay where you are and keep this phone with you."
    if lang.startswith("en"):
        return base
    try:
        out = await llm.complete([
            {"role": "system", "content": f"Translate into {LANG_NAMES.get(lang.split('-')[0], 'the same language')} "
                                          "for a frightened caller. Keep names and numbers. Output only the translation."},
            {"role": "user", "content": base},
        ], temperature=0.2, max_tokens=120)
    except Exception:
        return base
    text, _ = guard_reply(out, set(), eta, lang)
    return text or base


async def deliver_dispatch(store: Store, incident: Incident, llm,
                           live: dict[str, Callable[[str], Awaitable[None]]]) -> None:
    """Speaks the dispatch to every live caller of the incident; queues a callback for callers who hung up."""
    d = incident.dispatch or {}
    for cid in incident.call_ids:
        lang = store.call_lang(cid)
        text = await dispatch_line(llm, lang, d.get("team", "rescue team"), d.get("eta"))
        if cid in live:
            await live[cid](text)
        else:
            store.queue_callback(cid, text, lang)
