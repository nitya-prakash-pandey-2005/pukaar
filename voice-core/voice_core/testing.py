"""Offline fakes for tests and for running the apps without keys (DADI_FAKE=1 etc.)."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from .gnani.stt_stream import SttEvent


class FakeLLM:
    """Pops canned replies in order; returns "" when exhausted."""

    provider = "fake"
    model = "fake"

    def __init__(self, replies: list[str] | None = None):
        self.replies = list(replies or [])
        self.calls: list[list[dict]] = []

    def _next(self) -> str:
        return self.replies.pop(0) if self.replies else ""

    async def complete(self, messages, **kw) -> str:
        self.calls.append(messages)
        return self._next()

    async def stream(self, messages, **kw) -> AsyncIterator[str]:
        self.calls.append(messages)
        text = self._next()
        n = max(1, len(text) // 3)
        for i in range(0, len(text), n):
            await asyncio.sleep(0)
            yield text[i : i + n]


class FakeStt:
    """Mimics PrismaStream. Yields scripted events (optionally spaced by `gap` seconds).
    end="hold" keeps the stream open until close(); end="close" ends it (simulates a network drop)."""

    def __init__(self, events: list[SttEvent], *, gap: float = 0.0, end: str = "hold"):
        self._events = list(events)
        self.gap = gap
        self.end = end
        self.connected = False
        self.sent = 0
        self._closed = asyncio.Event()

    async def connect(self):
        self.connected = True

    async def send_audio(self, pcm16: bytes):
        self.sent += len(pcm16)

    async def commit(self):
        pass

    async def events(self) -> AsyncIterator[SttEvent]:
        for ev in self._events:
            if self.gap:
                await asyncio.sleep(self.gap)
            else:
                await asyncio.sleep(0)
            yield ev
        if self.end == "hold":
            await self._closed.wait()
        self.connected = False
        yield SttEvent("closed")

    async def close(self):
        self.connected = False
        self._closed.set()


async def fake_tts(*args, chunk_delay: float = 0.0, **kw) -> AsyncIterator[bytes]:
    """Two 320-byte PCM chunks per call, like a tiny Timbre stream."""
    for _ in range(2):
        if chunk_delay:
            await asyncio.sleep(chunk_delay)
        else:
            await asyncio.sleep(0)
        yield b"\x00\x01" * 160


def ev(type_: str, text: str = "", language: str | None = None) -> SttEvent:
    return SttEvent(type_, text=text, language=language)
