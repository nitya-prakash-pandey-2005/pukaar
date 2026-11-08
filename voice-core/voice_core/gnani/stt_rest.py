"""Prisma speech-to-text over REST (clips up to 30 seconds)."""

from __future__ import annotations

import json

import httpx

from .errors import GnaniError
from .stt_stream import SttEvent

STT_REST_URL = "https://api.vachana.ai/stt/v3"


async def transcribe_rest(
    api_key: str,
    wav: bytes,
    *,
    language_code: str = "hi-IN,en-IN",
    model: str = "prisma-v3.0",
    fmt: str = "codemix",
    keyterms: list[str] | None = None,
    timeout: float = 60.0,
    client: httpx.AsyncClient | None = None,
) -> SttEvent:
    data = {"model": model, "language_code": language_code, "format": fmt}
    if keyterms:
        data["keyterms"] = json.dumps(list(keyterms), ensure_ascii=False)
    files = {"audio_file": ("clip.wav", wav, "audio/wav")}
    headers = {"X-API-Key-ID": api_key}
    own = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    try:
        r = await client.post(STT_REST_URL, headers=headers, data=data, files=files)
    finally:
        if own:
            await client.aclose()
    if r.status_code != 200:
        raise GnaniError(r.status_code, r.text[:500])
    d = r.json()
    lat = d.get("end_to_end_latency")
    return SttEvent(
        type="transcript",
        text=(d.get("transcript") or "").strip(),
        language=d.get("detected_language_code"),
        latency_ms=float(lat) * 1000 if isinstance(lat, (int, float)) else None,
        raw=d,
    )
