"""Prisma realtime speech-to-text over WebSocket.

Protocol (docs.gnani.ai/api/STT/stt-websocket): settings travel as handshake headers; audio goes
up as binary frames of exactly 1024 bytes of PCM16 mono (512 samples) at real-time pace; the
server answers with JSON events (connected, speech_start, processing, transcript, error).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncIterator

import websockets

from ..audio import FrameBuffer

STT_WS_URL = "wss://api.vachana.ai/stt/v3/stream"
FRAME_BYTES = 1024
_KNOWN = {"connected", "speech_start", "processing", "transcript", "error", "settings_updated"}


@dataclass
class SttEvent:
    type: str
    text: str = ""
    language: str | None = None
    latency_ms: float | None = None
    raw: dict = field(default_factory=dict)


def build_stt_headers(
    api_key: str,
    *,
    language_code: str,
    model: str = "prisma-v3.0",
    sample_rate: int = 8000,
    fmt: str = "codemix",
    keyterms: list[str] | None = None,
    vad: dict[str, str] | None = None,
    idle_timeout_sec: int = 120,
) -> dict[str, str]:
    if "," in language_code:  # streaming rejects locale lists (checked 8 Nov 2026); REST still accepts them
        language_code = "indic-auto" if model == "prisma-v3.0" else language_code.split(",")[0].strip()
    h = {
        "x-api-key-id": api_key,
        "model": model,
        "language_code": language_code,
        "x-sample-rate": str(int(sample_rate)),
        "format": fmt,
        "x-idle-timeout-sec": str(int(idle_timeout_sec)),
    }
    if keyterms:
        h["keyterms"] = json.dumps(list(keyterms))  # \u-escaped: HTTP headers must be ASCII
    for k, v in (vad or {}).items():
        h[k] = str(v)
    return h


def parse_stt_message(msg: str) -> SttEvent:
    try:
        d = json.loads(msg)
    except (TypeError, ValueError):
        return SttEvent("error", raw={"message": f"unparseable: {str(msg)[:200]}"})
    if not isinstance(d, dict):
        return SttEvent("error", raw={"message": "non-object message"})
    t = d.get("type")
    if t not in _KNOWN:
        return SttEvent("error", raw=d)
    if t == "settings_updated":
        return SttEvent("connected", raw=d)
    lat = d.get("latency")
    return SttEvent(
        type=t,
        text=(d.get("text") or "").strip(),
        language=d.get("detected_language_code"),
        latency_ms=float(lat) if isinstance(lat, (int, float)) else None,
        raw=d,
    )


class PrismaStream:
    """One realtime STT session. Not thread-safe; use from one asyncio task for sending."""

    def __init__(self, api_key: str, *, url: str = STT_WS_URL, **header_kwargs):
        self.url = url
        self.headers = build_stt_headers(api_key, **header_kwargs)
        self.sample_rate = int(self.headers["x-sample-rate"])
        self._ws = None
        self._fb = FrameBuffer(FRAME_BYTES)
        self.connected = False

    async def connect(self, timeout: float = 15.0) -> None:
        self._ws = await websockets.connect(
            self.url,
            additional_headers=self.headers,
            max_size=None,
            open_timeout=timeout,
            ping_interval=20,
            ping_timeout=20,
        )
        self.connected = True

    async def send_audio(self, pcm16: bytes) -> None:
        if self._ws is None:
            raise RuntimeError("PrismaStream not connected")
        for frame in self._fb.push(pcm16):
            await self._ws.send(frame)

    async def send_pcm_realtime(self, pcm16: bytes, sample_rate: int | None = None) -> None:
        """Send pre-recorded audio paced like a live microphone (for drills and the arena)."""
        sr = sample_rate or self.sample_rate
        frame_dur = (FRAME_BYTES // 2) / sr
        loop = asyncio.get_running_loop()
        start = loop.time()
        frames = self._fb.push(pcm16)
        for i, frame in enumerate(frames):
            await self._ws.send(frame)
            delay = start + (i + 1) * frame_dur - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)

    async def commit(self) -> None:
        last = self._fb.flush()
        if last:
            await self._ws.send(last)
        await self._ws.send(json.dumps({"type": "commit"}))

    async def events(self) -> AsyncIterator[SttEvent]:
        code, reason = None, ""
        try:
            async for msg in self._ws:
                if isinstance(msg, (bytes, bytearray)):
                    continue
                yield parse_stt_message(msg)
        except websockets.ConnectionClosed as e:  # network drop or server close
            code, reason = getattr(e, "code", None), str(e)
        finally:
            self.connected = False
        yield SttEvent("closed", raw={"code": code, "reason": reason})

    async def close(self) -> None:
        self.connected = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
