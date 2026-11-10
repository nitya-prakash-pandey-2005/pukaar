"""Gnani clients without the network: Timbre REST, voice-clone embedding and clone TTS through httpx.MockTransport,
and the Prisma realtime stream through a fake WebSocket (connect options, closing, drops, pacing)."""

import asyncio
import base64
import json

import httpx
import pytest
import websockets
from websockets.frames import Close

from voice_core.gnani import GnaniError, gate, stt_stream
from voice_core.gnani import tts as tts_mod
from voice_core.gnani.stt_stream import FRAME_BYTES, PrismaStream


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(gate, "RETRY_DELAYS", (0.0, 0.0, 0.0))


@pytest.fixture
def mock_http(monkeypatch):
    """Route every httpx.AsyncClient made inside the TTS module to a handler; returns the list of requests seen."""
    real = httpx.AsyncClient
    state = {"handler": None, "requests": []}

    def handler(req):
        state["requests"].append(req)
        return state["handler"](req)

    monkeypatch.setattr(tts_mod.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return state


# -- Timbre REST, voice-clone embedding, clone TTS -------------------------------------------------------------------


async def test_tts_rest_posts_the_documented_body_and_returns_pcm(mock_http):
    mock_http["handler"] = lambda r: httpx.Response(200, content=b"\x01\x00" * 4,
                                                    headers={"content-type": "application/octet-stream"})
    pcm = await tts_mod.tts_rest("key-1", "Namaste", voice="Lakshmi", language="hi-IN", sample_rate=8000)
    assert pcm == b"\x01\x00" * 4
    req = mock_http["requests"][0]
    assert str(req.url) == tts_mod.TTS_REST_URL and req.headers["X-API-Key-ID"] == "key-1"
    body = json.loads(req.content)
    assert body == tts_mod.build_tts_body("Namaste", voice="Lakshmi", language="hi-IN", sample_rate=8000)


async def test_tts_rest_treats_a_json_reply_as_an_error_even_with_200(mock_http):
    mock_http["handler"] = lambda r: httpx.Response(200, json={"error": "voice not found"})
    with pytest.raises(GnaniError) as exc:
        await tts_mod.tts_rest("k", "hi", voice="Nobody")
    assert "voice not found" in exc.value.body


async def test_tts_rest_retries_a_rate_limit(mock_http):
    replies = iter([httpx.Response(429, text="RATE_LIMITED"),
                    httpx.Response(200, content=b"\x00\x00", headers={"content-type": "audio/raw"})])
    mock_http["handler"] = lambda r: next(replies)
    assert await tts_mod.tts_rest("k", "hi", voice="Lakshmi") == b"\x00\x00"
    assert len(mock_http["requests"]) == 2


@pytest.mark.parametrize("reply", [
    {"embedding": "QUJD", "shape": [1, 768], "dtype": "float32"},
    {"success": True, "data": {"voice_clone_embedding": {"embedding": "QUJD", "shape": [1, 768], "dtype": "float32"}}},
])
async def test_create_voice_embedding_accepts_both_documented_shapes(mock_http, reply):
    mock_http["handler"] = lambda r: httpx.Response(200, json=reply)
    emb = await tts_mod.create_voice_embedding("k", b"RIFFwav")
    assert emb == {"embedding": "QUJD", "shape": [1, 768], "dtype": "float32"}
    req = mock_http["requests"][0]
    assert str(req.url) == tts_mod.VC_EMBED_URL and b'filename="voice.wav"' in req.content


async def test_create_voice_embedding_raises_on_http_error(mock_http):
    mock_http["handler"] = lambda r: httpx.Response(400, text="audio too short")
    with pytest.raises(GnaniError) as exc:
        await tts_mod.create_voice_embedding("k", b"x")
    assert exc.value.status == 400


async def test_tts_clone_rest_body(mock_http):
    mock_http["handler"] = lambda r: httpx.Response(200, content=b"\x02\x00", headers={"content-type": "audio/raw"})
    emb = {"embedding": "QUJD", "shape": [1, 768], "dtype": "float32"}
    assert await tts_mod.tts_clone_rest("k", "Haan beta", emb) == b"\x02\x00"
    assert await tts_mod.tts_clone_rest("k", "Haan beta", emb, language="hi-IN", sample_rate=8000) == b"\x02\x00"
    first, second = (json.loads(r.content) for r in mock_http["requests"])
    assert first["model"] == "vachana-vc-v1" and first["speaker_embedding"] == emb
    assert first["audio_config"]["sample_rate"] == 16000 and "language" not in first
    assert second["language"] == "hi-IN" and second["audio_config"]["sample_rate"] == 8000


async def test_clone_cache_pays_once_per_text_and_voice(tmp_path, monkeypatch):
    calls = []

    async def fake_clone(api_key, text, embedding, **kw):
        calls.append(text)
        return b"\x03\x00"

    monkeypatch.setattr(tts_mod, "tts_clone_rest", fake_clone)
    cache = tts_mod.TtsCache(tmp_path)
    emb_a, emb_b = {"embedding": "AAAA"}, {"embedding": "BBBB"}
    for _ in range(2):
        assert await cache.get_or_make_clone("k", "Haan", emb_a, sample_rate=8000) == b"\x03\x00"
    await cache.get_or_make_clone("k", "Haan", emb_b, sample_rate=8000)
    assert calls == ["Haan", "Haan"]  # second call for emb_a was a cache hit; emb_b is a different voice


# -- Prisma realtime stream -----------------------------------------------------------------------------------------


class FakeWS:
    def __init__(self, incoming=(), drop: Exception | None = None):
        self.sent, self.closed = [], False
        self._incoming, self._drop = list(incoming), drop

    async def send(self, m):
        self.sent.append(m)

    async def close(self):
        self.closed = True
        raise RuntimeError("already closed")  # close() must swallow this

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._incoming:
            return self._incoming.pop(0)
        if self._drop:
            raise self._drop
        raise StopAsyncIteration


async def test_connect_sends_the_auth_headers_and_keepalive(monkeypatch):
    seen = {}

    async def fake_connect(url, **kw):
        seen["url"] = url
        seen.update(kw)
        return FakeWS()

    monkeypatch.setattr(stt_stream.websockets, "connect", fake_connect)
    s = PrismaStream("KEY", language_code="hi-IN", sample_rate=8000)
    await s.connect(timeout=3)
    assert s.connected and seen["url"] == stt_stream.STT_WS_URL
    assert seen["additional_headers"] == s.headers and seen["open_timeout"] == 3
    assert seen["ping_interval"] == 20 and seen["max_size"] is None
    await s.close()  # the fake's close() raises; PrismaStream swallows it
    assert not s.connected and s._ws.closed


async def test_send_before_connect_is_an_error():
    with pytest.raises(RuntimeError):
        await PrismaStream("KEY", language_code="hi-IN").send_audio(b"\x00\x00")


async def test_events_skip_binary_and_report_a_network_drop():
    s = PrismaStream("KEY", language_code="hi-IN")
    drop = websockets.ConnectionClosed(Close(1011, "server error"), None)
    s._ws = FakeWS([b"\x00\x01", json.dumps({"type": "transcript", "text": " theek hai "})], drop=drop)
    s.connected = True
    events = [e async for e in s.events()]
    assert [e.type for e in events] == ["transcript", "closed"]
    assert events[0].text == "theek hai"
    assert "1011" in events[1].raw["reason"] and not s.connected


async def test_send_pcm_realtime_paces_frames_like_a_microphone():
    s = PrismaStream("KEY", language_code="hi-IN", sample_rate=16000)
    s._ws = FakeWS()
    pcm = b"\x00" * (FRAME_BYTES * 4)  # 4 frames of 32 ms at 16 kHz = 128 ms
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    await s.send_pcm_realtime(pcm)
    elapsed = loop.time() - t0
    assert [len(f) for f in s._ws.sent] == [FRAME_BYTES] * 4
    assert elapsed >= 0.1  # not dumped faster than real time


def test_embedding_round_trip_shape():
    raw = base64.b64encode(b"\x00" * 16).decode()
    assert tts_mod.normalise_embedding({"embedding": raw, "shape": [1, 4], "dtype": "float32", "x": 1}) == {
        "embedding": raw, "shape": [1, 4], "dtype": "float32"}
