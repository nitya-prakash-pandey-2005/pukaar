"""Turn-taking helpers: sentence splitting for streamed replies, echo and silence guards,
and the turn-based STT fallback (energy VAD + Prisma REST) for accounts limited to one active request."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from difflib import SequenceMatcher
from typing import AsyncIterator

import numpy as np

from .audio import pcm16_to_float, wav_bytes
from .gnani.stt_rest import transcribe_rest
from .gnani.stt_stream import SttEvent
from .gnani.tts import strip_audio_tags

_ENDERS = ".!?।॥…"
_BOUNDARY = re.compile(r"([.!?।॥…]+[\"')\]]*)(\s+)|\n+")


def split_sentences(buf: str, final: bool = False) -> tuple[list[str], str]:
    """Split complete sentences off the front of a streaming buffer.
    A sentence ends at . ! ? । ॥ … followed by whitespace, or at a newline. With final=True the
    remainder is returned as a last sentence. Pieces shorter than 2 characters merge forward."""
    out: list[str] = []
    pos = 0
    carry = ""
    for m in _BOUNDARY.finditer(buf):
        end = m.end(1) if m.group(1) else m.start()
        piece = (carry + buf[pos:end]).strip()
        pos = m.end()
        if len(piece) < 2:
            carry = piece + " " if piece else ""
            continue
        out.append(piece)
        carry = ""
    rest = (carry + buf[pos:]).lstrip()
    if final and rest.strip():
        out.append(rest.strip())
        rest = ""
    return out, rest


def _norm(text: str) -> str:
    t = strip_audio_tags(text or "").lower()
    t = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in t)
    return re.sub(r"\s+", " ", t).strip()


def is_meaningful(text: str) -> bool:
    return len(_norm(text).replace(" ", "")) >= 2


def is_echo(text: str, recent_agent_lines: list[str], threshold: float = 0.6) -> bool:
    """True when a transcript is (mostly) the agent's own recent speech picked up by the mic."""
    t = _norm(text)
    if not t:
        return False
    for line in recent_agent_lines[-2:]:
        a = _norm(line)
        if not a:
            continue
        if SequenceMatcher(None, t, a).ratio() >= threshold:
            return True
        if len(t.split()) >= 3 and (t in a or a in t):
            return True
    return False


class TurnBasedStt:
    """Same events() interface as PrismaStream, but: local energy VAD decides utterance ends and each
    utterance is sent to Prisma REST. Never more than one Gnani request in flight from this object."""

    def __init__(self, api_key: str, *, language_code: str = "hi-IN,en-IN", model: str = "prisma-v3.0",
                 sample_rate: int = 8000, fmt: str = "codemix", keyterms: list[str] | None = None,
                 start_rms: float = 0.015, start_ms: int = 200, end_ms: int = 600, max_s: float = 25.0, **_):
        self.api_key, self.language_code, self.model, self.fmt = api_key, language_code, model, fmt
        self.sample_rate, self.keyterms = sample_rate, keyterms
        self.start_rms, self.start_ms, self.end_ms, self.max_s = start_rms, start_ms, end_ms, max_s
        self.connected = False
        self._q: asyncio.Queue[SttEvent | None] = asyncio.Queue()
        self._buf = bytearray()
        self._speaking = False
        self._voiced_ms = 0.0
        self._silent_ms = 0.0
        self.busy = asyncio.Lock()  # held while a REST request is in flight

    async def connect(self):
        self.connected = True
        await self._q.put(SttEvent("connected"))

    async def send_audio(self, pcm16: bytes) -> None:
        x = pcm16_to_float(pcm16)
        if not len(x):
            return
        ms = 1000 * len(x) / self.sample_rate
        loud = float(np.sqrt(np.mean(x**2))) > self.start_rms
        if self._speaking:
            self._buf.extend(pcm16)
            self._silent_ms = 0 if loud else self._silent_ms + ms
            if self._silent_ms >= self.end_ms or len(self._buf) / 2 / self.sample_rate > self.max_s:
                await self._finish()
        else:
            self._voiced_ms = self._voiced_ms + ms if loud else 0
            self._buf.extend(pcm16)
            keep = int(self.sample_rate * 2 * 0.4)  # keep 400 ms of pre-roll
            if len(self._buf) > keep:
                del self._buf[: len(self._buf) - keep]
            if self._voiced_ms >= self.start_ms:
                self._speaking, self._silent_ms = True, 0
                await self._q.put(SttEvent("speech_start"))

    async def _finish(self):
        audio = bytes(self._buf)
        self._buf.clear()
        self._speaking, self._voiced_ms, self._silent_ms = False, 0, 0
        await self._q.put(SttEvent("processing"))
        asyncio.create_task(self._transcribe(audio))

    async def _transcribe(self, audio: bytes):
        async with self.busy:
            try:
                ev = await transcribe_rest(self.api_key, wav_bytes(audio, self.sample_rate), language_code=self.language_code,
                                           model=self.model, fmt=self.fmt, keyterms=self.keyterms)
                await self._q.put(ev)
            except Exception as e:  # keep the session alive
                await self._q.put(SttEvent("error", raw={"message": repr(e)}))

    async def commit(self):
        if self._speaking and self._buf:
            await self._finish()

    async def events(self) -> AsyncIterator[SttEvent]:
        while True:
            ev = await self._q.get()
            if ev is None:
                break
            yield ev
        yield SttEvent("closed")

    async def close(self):
        self.connected = False
        await self._q.put(None)
