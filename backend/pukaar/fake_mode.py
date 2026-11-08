"""PUKAAR_FAKE=1: run the whole app with no API keys. A scripted caller speaks every few seconds."""

from __future__ import annotations

import asyncio
import itertools
import json

import numpy as np
from voice_core.audio import float_to_pcm16
from voice_core.gnani.stt_stream import SttEvent

SCRIPT = [
    "Hello, Velachery la irukom, veedu full ah thanni vandhuruchu!",
    "Naanga naalu peru, ellarum roof mela irukom.",
    "En paati ku sugar irukku, insulin podanum.",
    "Thanni chest varaikkum vandhuruchu, romba bayama irukku.",
]
FACTS = [  # cumulative facts "extracted" after each scripted line
    {"hazard": "flood", "locality": "Velachery", "caller_language": "ta-IN"},
    {"people_count": 4, "on_roof": True},
    {"vulnerable": ["elderly"], "medical_needs": ["insulin"]},
    {"water_level": "chest"},
]
REPLIES = [
    "பயப்படாதீங்க, நான் இருக்கேன். உங்க கூட எத்தனை பேர் இருக்காங்க?",
    "சரி, கவலைப்படாதீங்க. யாருக்காவது அடிபட்டிருக்கா, மருந்து வேணுமா?",
    "புரியுது. தண்ணி எவ்வளவு உயரம் வந்திருக்கு?",
    "நீங்க மேப்ல தெரியறீங்க. மேலேயே இருங்க.",
]


class FakeTriageLLM:
    """Extraction prompts get the next scripted facts; translations echo; replies cycle."""

    provider = "fake"
    model = "fake"

    def __init__(self):
        self._facts = iter(FACTS)
        self._replies = itertools.cycle(REPLIES)

    async def complete(self, messages, **kw) -> str:
        await asyncio.sleep(0.2)
        system = messages[0]["content"]
        if system.startswith("You extract facts"):
            return json.dumps(next(self._facts, {}))
        if system.startswith("Translate"):
            return messages[-1]["content"]
        return next(self._replies)


class ScriptedStt:
    """Ignores audio; 'hears' the next scripted caller line every `every` seconds."""

    def __init__(self, every: float = 6.0):
        self.every = every
        self.connected = False
        self._closed = asyncio.Event()

    async def connect(self):
        self.connected = True

    async def send_audio(self, pcm16: bytes):
        pass

    async def commit(self):
        pass

    async def events(self):
        yield SttEvent("connected")
        for line in SCRIPT:
            try:
                await asyncio.wait_for(self._closed.wait(), timeout=self.every)
                break
            except asyncio.TimeoutError:
                pass
            yield SttEvent("speech_start")
            await asyncio.sleep(0.8)
            yield SttEvent("processing")
            await asyncio.sleep(0.3)
            yield SttEvent("transcript", text=line, language="ta-IN", latency_ms=180.0)
        await self._closed.wait()
        yield SttEvent("closed")

    async def close(self):
        self.connected = False
        self._closed.set()


async def tone_tts(api_key, text, sample_rate: int = 8000, **kw):
    """A soft 330 Hz hum whose length follows the text (stands in for Timbre audio)."""
    secs = min(4.0, 0.05 * len(text) + 0.4)
    t = np.arange(int(secs * sample_rate)) / sample_rate
    x = 0.08 * np.sin(2 * np.pi * 330 * t) * np.minimum(1, np.minimum(t, secs - t) * 8)
    pcm = float_to_pcm16(x.astype(np.float32))
    step = sample_rate // 5 * 2
    for i in range(0, len(pcm), step):
        await asyncio.sleep(0.02)
        yield pcm[i : i + step]
