"""Rescuer <-> caller interpreter: a rescue team from another state speaks Hindi or English, the trapped caller hears
it in Tamil, Telugu, Hindi or English (Timbre), and the caller's answer comes back translated. Machine
interpretation, half-duplex: one side holds the floor at a time.

One turn = push-to-talk clip -> Prisma (one locale) -> ONE short LLM translation -> Timbre in the listener's language.
The translation is checked like every line Pukaar speaks: it may not add a time promise, a "you are safe" or a number
the speaker did not say (guard.adds_nothing), and it may not drop a number the speaker did say. If it fails a check
(or the LLM fails), the listener hears the speaker's own words, and both captions carry a note saying so."""

from __future__ import annotations

import re
import time
from typing import Awaitable, Callable

from .guard import _numbers, adds_nothing
from .triage import LANG_NAMES

ROLES = ("rescuer", "caller")
OTHER = {"rescuer": "caller", "caller": "rescuer"}
LANGS = {"rescuer": ("hi-IN", "en-IN"), "caller": ("ta-IN", "te-IN", "hi-IN", "en-IN")}
DEFAULT_LANGS = {"rescuer": "hi-IN", "caller": "ta-IN"}
# the voice each LISTENER hears: the caller hears Pukaar's own voice, the rescuer a different (male) one,
# so in a one-browser demo nobody confuses whose words are whose
LISTENER_VOICE = {"caller": "Chetana", "rescuer": "Prakash"}
MAX_CLIP_BYTES = 30 * 16000 * 2  # Prisma REST takes clips up to 30 s (16 kHz PCM16 is the most we ever send)

NOTE_ADDED = "Machine translation withheld: it added a time, a number or a \"you are safe\" the speaker did not say. Original words spoken instead."
NOTE_LOST = "Machine translation withheld: it dropped a number the speaker said. Original words spoken instead."
NOTE_FAILED = "Translation unavailable: original words spoken instead."

Transcribe = Callable[[bytes, str, str], Awaitable[tuple[str, float | None]]]  # (wav, locale, role) -> (text, Prisma ms)
Speak = Callable[[str, str, str], Awaitable[tuple[str, float]]]  # (text, locale, voice) -> (audio url, seconds)

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)
_LABEL_RE = re.compile(r"^\s*(?:translation|अनुवाद)\s*:\s*", re.I)


def _name(lang: str) -> str:
    return LANG_NAMES.get(lang.split("-")[0], lang)


def translate_messages(text: str, src: str, dst: str, speaker: str) -> list[dict]:
    listener = OTHER.get(speaker, "listener")
    return [
        {"role": "system", "content": (
            f"Translate what the {speaker} said from {_name(src)} into {_name(dst)}, to be spoken to the {listener} "
            "during a flood rescue. Spoken, simple words. Keep every name, place, landmark and number exactly "
            "(write numbers as digits). Never add facts, times, promises or reassurance that are not in the original; "
            "translate questions as questions. Output only the translation.")},
        {"role": "user", "content": text},
    ]


def clean(out: str) -> str:
    out = _LABEL_RE.sub("", _THINK_RE.sub("", out or "")).strip()
    return out.strip("\"'“”‘’").strip()


def check(src: str, out: str) -> str | None:
    """None if `out` is a faithful-enough rendering of `src` to speak; else the note that says why it was withheld."""
    if not adds_nothing(src, out):
        return NOTE_ADDED
    if not _numbers(src) <= _numbers(out):  # "3 people on the roof" must not become "people on the roof"
        return NOTE_LOST
    return None


async def translate(llm, text: str, src: str, dst: str, speaker: str = "rescuer") -> tuple[str, str | None]:
    """(text to speak, note). One short LLM call; any failure or added fact gives back the speaker's own words."""
    if src.split("-")[0] == dst.split("-")[0]:
        return text, None
    try:
        out = clean(await llm.complete(translate_messages(text, src, dst, speaker), temperature=0.1, max_tokens=200))
    except Exception:
        return text, NOTE_FAILED
    if not out:
        return text, NOTE_FAILED
    note = check(text, out)
    return (text, note) if note else (out, None)


class Interpreter:
    """One interpreter session. `claim` / `release` implement the speaking lock; `turn` interprets one clip."""

    def __init__(self, *, transcribe: Transcribe, llm, speak: Speak, rescuer_lang: str = DEFAULT_LANGS["rescuer"],
                 caller_lang: str = DEFAULT_LANGS["caller"], clock: Callable[[], float] = time.monotonic):
        self.transcribe, self.llm, self.speak, self.clock = transcribe, llm, speak, clock
        self.langs: dict[str, str] = {}
        self.set_lang("rescuer", rescuer_lang)
        self.set_lang("caller", caller_lang)
        self.speaking: str | None = None  # role holding the floor: talking, or its words being interpreted
        self.playing: str | None = None  # role whose translation is being played to the other side
        self.play_until = 0.0
        self.turns: list[dict] = []

    def set_lang(self, role: str, lang: str) -> None:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        if lang not in LANGS[role]:
            raise ValueError(f"{role} language must be one of {', '.join(LANGS[role])}")
        self.langs[role] = lang

    def state(self) -> dict:
        return {"type": "langs", "langs": dict(self.langs), "voices": dict(LISTENER_VOICE),
                "choices": {r: list(v) for r, v in LANGS.items()}}

    def claim(self, role: str) -> dict:
        """Push-to-talk pressed. Busy while the other side holds the floor; pressing while the other side's
        translation is still playing is a barge-in (allowed: the client stops that audio)."""
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        if self.speaking not in (None, role):
            return {"type": "busy", "role": role, "speaking": self.speaking}
        barge = self.speaking is None and self.playing is not None and self.clock() < self.play_until
        stopped = self.playing if barge else None
        self.speaking, self.playing, self.play_until = role, None, 0.0
        return {"type": "floor", "role": role, "barge_in": barge, "stop_audio_of": stopped}

    def release(self, role: str) -> None:
        if self.speaking == role:
            self.speaking = None

    async def turn(self, role: str, wav: bytes) -> dict:
        """The floor holder's clip -> caption pair + the listener's audio. Always gives the floor back."""
        if self.speaking != role:
            raise ValueError(f"{role} does not hold the floor")
        src, dst = self.langs[role], self.langs[OTHER[role]]
        try:
            t0 = self.clock()
            text, prisma_ms = await self.transcribe(wav, src, role)
            text = (text or "").strip()
            t1 = self.clock()
            base = {"type": "turn", "id": len(self.turns) + 1, "role": role, "src_lang": src, "dst_lang": dst,
                    "original": text, "prisma_ms": None if prisma_ms is None else round(prisma_ms),
                    "stt_ms": round((t1 - t0) * 1000)}
            if not text:
                return {**base, "type": "unheard"}
            out, note = await translate(self.llm, text, src, dst, role)
            t2 = self.clock()
            spoken_lang = src if note else dst  # withheld: the speaker's own words, pronounced as their language
            url, secs = await self.speak(out, spoken_lang, LISTENER_VOICE[OTHER[role]])
            t3 = self.clock()
            msg = {**base, "translation": out, "translated": note is None, "note": note, "spoken_lang": spoken_lang,
                   "voice": LISTENER_VOICE[OTHER[role]], "audio_url": url, "audio_s": round(secs, 2),
                   "translate_ms": round((t2 - t1) * 1000), "tts_ms": round((t3 - t2) * 1000),
                   "total_ms": round((t3 - t0) * 1000)}
            self.turns.append(msg)
            self.playing, self.play_until = role, self.clock() + secs
            return msg
        finally:
            self.release(role)


# ---------------------------------------------------------------- fake mode (PUKAAR_FAKE=1 / tests)
FAKE_LINES = {  # what the fake Prisma "hears" from each side, in order, and the fake translations
    "rescuer": ["हम नाव लेकर आ रहे हैं। आपके घर के पास कौन सी बड़ी इमारत है?", "आपके साथ कितने लोग हैं?"],
    "caller": ["வேளச்சேரி பஸ் டிப்போ பக்கத்துல இருக்கோம், மூணாவது மாடி.", "நாங்க 4 பேர் இருக்கோம்."],
}
FAKE_TRANSLATIONS = {
    FAKE_LINES["rescuer"][0]: "நாங்க படகுடன் வருகிறோம். உங்க வீட்டுக்கு பக்கத்துல எந்த பெரிய கட்டிடம் இருக்கு?",
    FAKE_LINES["rescuer"][1]: "உங்க கூட எத்தனை பேர் இருக்காங்க?",
    FAKE_LINES["caller"][0]: "हम वेलाचेरी बस डिपो के पास हैं, तीसरी मंज़िल पर।",
    FAKE_LINES["caller"][1]: "हम 4 लोग हैं।",
}


class FakeTranscriber:
    def __init__(self):
        self.n = {r: 0 for r in ROLES}

    async def __call__(self, wav: bytes, lang: str, role: str) -> tuple[str, float | None]:
        lines = FAKE_LINES[role]
        line = lines[self.n[role] % len(lines)]
        self.n[role] += 1
        return line, 180.0


class FakeInterpLLM:
    provider = model = "fake"

    async def complete(self, messages, **kw) -> str:
        text = messages[-1]["content"]
        return FAKE_TRANSLATIONS.get(text, text)
