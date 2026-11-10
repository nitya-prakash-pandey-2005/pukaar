"""Timbre text-to-speech: REST and WebSocket streaming, plus Gnani voice cloning."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import AsyncIterator

import httpx
import websockets

from . import gate
from .errors import GnaniError

TTS_REST_URL = "https://api.vachana.ai/api/v1/tts/inference"
TTS_WS_URL = "wss://api.vachana.ai/api/v1/tts"
VC_EMBED_URL = "https://api.vachana.ai/api/v1/tts/voice-clone/embeddings"
RECV_TIMEOUT = 8.0  # seconds between Timbre stream messages before we give up (frees the gate, runs the fallback)

AUDIO_TAGS = (
    "laugh", "giggle", "sigh", "exhales", "sniffles", "yawns", "coughs",
    "clears throat", "whispers", "shouting", "excited", "slow", "pauses",
)
_TAG_RE = re.compile(r"\s*<(?:" + "|".join(re.escape(t) for t in AUDIO_TAGS) + r")>\s*")

_ws_connect = websockets.connect  # patched in tests
log = logging.getLogger(__name__)


class TtsError(Exception):
    pass


def strip_audio_tags(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _TAG_RE.sub(" ", text)).strip()


def build_tts_body(
    text: str,
    *,
    voice: str,
    model: str = "timbre-v3.0",
    language: str = "hi-IN",
    speed: float = 1.0,
    sample_rate: int = 8000,
    container: str = "raw",
) -> dict:
    audio_config = {
        "sample_rate": int(sample_rate),
        "num_channels": 1,
        "sample_width": 2,
        "encoding": "linear_pcm",
        "container": container,
    }
    if container == "mp3":
        audio_config.pop("encoding")
        audio_config["bitrate"] = "128k"
    return {
        "text": text,
        "voice": voice,
        "model": model,
        "language": language,
        "speed": float(speed),
        "audio_config": audio_config,
    }


async def tts_rest(api_key: str, text: str, *, timeout: float = 60.0, **body_kwargs) -> bytes:
    """Returns the audio bytes (raw PCM16 when container is "raw")."""
    body = build_tts_body(text, **body_kwargs)
    return await _post_tts(api_key, body, timeout)


async def _post_tts(api_key: str, body: dict, timeout: float) -> bytes:
    return await gate.gnani_call(_post_tts_once, api_key, body, timeout)


async def _post_tts_once(api_key: str, body: dict, timeout: float) -> bytes:
    headers = {"X-API-Key-ID": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(TTS_REST_URL, headers=headers, json=body)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or ctype.startswith("application/json"):
        raise GnaniError(r.status_code, r.text[:500])
    return r.content


async def tts_stream(api_key: str, text: str, **body_kwargs) -> AsyncIterator[bytes]:
    """Streams PCM chunks from Timbre's WebSocket. Chunks are kept 2-byte aligned.

    Holds the Gnani gate while streaming; a rate limit before the first chunk is retried with backoff."""
    body = build_tts_body(text, **body_kwargs)
    delays = gate.RETRY_DELAYS
    for attempt in range(len(delays) + 1):
        started = False
        try:
            async with gate.gnani_slot():
                async for chunk in _tts_stream_once(api_key, body):
                    started = True
                    yield chunk
            return
        except Exception as e:
            if started or attempt == len(delays) or not gate.is_rate_limit(e):
                raise
            log.info("TTS stream busy (%r); retry %d in %.1fs", e, attempt + 1, delays[attempt])
        await asyncio.sleep(delays[attempt])


async def _tts_stream_once(api_key: str, body: dict) -> AsyncIterator[bytes]:
    headers = {"X-API-Key-ID": api_key, "Content-Type": "application/json"}
    carry = b""
    async with _ws_connect(TTS_WS_URL, additional_headers=headers, max_size=None, open_timeout=15) as ws:
        await ws.send(json.dumps(body, ensure_ascii=False))
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), RECV_TIMEOUT)
            except asyncio.TimeoutError:
                raise TtsError(f"TTS stream stalled (no message for {RECV_TIMEOUT:.0f} s)") from None
            if isinstance(msg, (bytes, bytearray)):
                data = carry + bytes(msg)
            else:
                d = json.loads(msg)
                t = d.get("type")
                if t == "error":
                    raise TtsError(d.get("message") or d.get("error") or "TTS error")
                if t == "complete":
                    break
                if t != "audio":
                    continue
                b64 = (d.get("data") or {}).get("audio") or ""
                if not b64:
                    continue
                data = carry + base64.b64decode(b64)
            cut = len(data) - (len(data) % 2)
            carry = data[cut:]
            if cut:
                yield data[:cut]


# ---------------------------------------------------------------- voice cloning

def normalise_embedding(resp: dict) -> dict:
    """Gnani documents two response shapes; return {embedding, shape, dtype}."""
    if isinstance(resp, dict) and "embedding" in resp:
        return {k: resp[k] for k in ("embedding", "shape", "dtype") if k in resp}
    inner = ((resp or {}).get("data") or {}).get("voice_clone_embedding")
    if isinstance(inner, dict) and "embedding" in inner:
        return {k: inner[k] for k in ("embedding", "shape", "dtype") if k in inner}
    raise ValueError("no voice embedding in response")


async def create_voice_embedding(api_key: str, wav: bytes, *, timeout: float = 90.0) -> dict:
    return await gate.gnani_call(_create_voice_embedding_once, api_key, wav, timeout)


async def _create_voice_embedding_once(api_key: str, wav: bytes, timeout: float) -> dict:
    headers = {"X-API-Key-ID": api_key}
    files = {"audio_file": ("voice.wav", wav, "audio/wav")}
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(VC_EMBED_URL, headers=headers, files=files)
    if r.status_code != 200:
        raise GnaniError(r.status_code, r.text[:500])
    return normalise_embedding(r.json())


async def tts_clone_rest(
    api_key: str,
    text: str,
    embedding: dict,
    *,
    language: str | None = None,
    sample_rate: int = 16000,
    container: str = "raw",
    timeout: float = 90.0,
) -> bytes:
    body = {
        "text": text,
        "model": "vachana-vc-v1",
        "speaker_embedding": embedding,
        "audio_config": {
            "sample_rate": int(sample_rate),
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": container,
        },
    }
    if language:
        body["language"] = language
    return await _post_tts(api_key, body, timeout)


# ---------------------------------------------------------------- cache

class TtsCache:
    """Disk cache so the same sentence in the same voice is only ever paid for once."""

    def __init__(self, cache_dir: Path | str):
        self.dir = Path(cache_dir) / "tts"
        self.dir.mkdir(parents=True, exist_ok=True)

    def key(self, text: str, **kw) -> str:
        blob = json.dumps({"text": text, **kw}, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()

    def path(self, key: str) -> Path:
        return self.dir / f"{key}.bin"

    def get(self, key: str) -> bytes | None:
        p = self.path(key)
        return p.read_bytes() if p.exists() else None

    def put(self, key: str, data: bytes) -> None:
        self.path(key).write_bytes(data)

    async def get_or_make(self, api_key: str, text: str, **body_kwargs) -> bytes:
        k = self.key(text, **body_kwargs)
        hit = self.get(k)
        if hit is not None:
            return hit
        data = await tts_rest(api_key, text, **body_kwargs)
        self.put(k, data)
        return data

    async def get_or_make_clone(self, api_key: str, text: str, embedding: dict, **kw) -> bytes:
        emb_id = hashlib.sha1(str(embedding.get("embedding", ""))[:4096].encode()).hexdigest()[:12]
        k = self.key(text, clone=emb_id, **kw)
        hit = self.get(k)
        if hit is not None:
            return hit
        data = await tts_clone_rest(api_key, text, embedding, **kw)
        self.put(k, data)
        return data
