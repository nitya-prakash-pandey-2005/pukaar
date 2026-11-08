import base64
import json

import pytest

from voice_core.gnani import (
    PrismaStream,
    build_stt_headers,
    build_tts_body,
    normalise_embedding,
    parse_stt_message,
    strip_audio_tags,
)
from voice_core.gnani import tts as tts_mod


def test_stt_headers_contain_required_fields():
    h = build_stt_headers(
        "KEY", language_code="hi-IN,en-IN", keyterms=["CBI", "UPI"], vad={"x-min-silence-ms": "500"}
    )
    assert h["x-api-key-id"] == "KEY" and h["model"] == "prisma-v3.0"
    assert h["x-sample-rate"] == "8000" and h["format"] == "codemix"
    assert json.loads(h["keyterms"]) == ["CBI", "UPI"] and h["x-min-silence-ms"] == "500"
    assert h["language_code"] == "indic-auto"  # streaming takes exactly one locale (or indic-auto on v3.0)
    assert all(isinstance(v, str) for v in h.values())


def test_stt_headers_single_locale_and_ascii():
    assert build_stt_headers("K", language_code="ta-IN")["language_code"] == "ta-IN"
    assert build_stt_headers("K", language_code="ta-IN,hi-IN", model="prisma-v2.5")["language_code"] == "ta-IN"
    h = build_stt_headers("K", language_code="ta-IN", keyterms=["வெள்ளம்", "बाढ़"])
    assert json.loads(h["keyterms"]) == ["வெள்ளம்", "बाढ़"] and all(v.isascii() for v in h.values())


def test_parse_transcript_message():
    e = parse_stt_message(
        json.dumps(
            {"type": "transcript", "text": "aap CBI se ho?", "latency": 180,
             "detected_language_code": "hi-IN", "is_final": True}
        )
    )
    assert (e.type, e.text, e.language, e.latency_ms) == ("transcript", "aap CBI se ho?", "hi-IN", 180)


def test_parse_unknown_and_bad_messages():
    assert parse_stt_message("not json").type == "error"
    assert parse_stt_message(json.dumps({"type": "weird"})).type == "error"
    assert parse_stt_message(json.dumps({"type": "speech_start"})).type == "speech_start"


def test_tts_body_defaults():
    b = build_tts_body("नमस्ते <coughs> बेटा", voice="Lakshmi")
    assert b["model"] == "timbre-v3.0" and b["voice"] == "Lakshmi"
    assert b["audio_config"]["sample_rate"] == 8000
    assert b["audio_config"]["container"] == "raw" and b["audio_config"]["encoding"] == "linear_pcm"


def test_strip_audio_tags():
    assert strip_audio_tags("हाँ <coughs> बेटा <clears throat>बोलो") == "हाँ बेटा बोलो"


def test_normalise_embedding_both_shapes():
    flat = {"embedding": "abc", "shape": [1, 768], "dtype": "torch.bfloat16"}
    nested = {"success": True, "data": {"voice_clone_embedding": flat}}
    assert normalise_embedding(flat) == flat and normalise_embedding(nested) == flat
    with pytest.raises(ValueError):
        normalise_embedding({"success": True})


class FakeWS:
    def __init__(self, incoming=None):
        self.sent = []
        self._incoming = list(incoming or [])

    async def send(self, m):
        self.sent.append(m)

    async def recv(self):
        return self._incoming.pop(0)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._incoming:
            raise StopAsyncIteration
        return self._incoming.pop(0)

    async def close(self):
        pass


async def test_prisma_stream_frames_and_commit():
    s = PrismaStream("KEY", language_code="hi-IN")
    s._ws = FakeWS([json.dumps({"type": "transcript", "text": "haan"})])
    s.connected = True
    await s.send_audio(b"\x00" * 1500)
    assert [len(x) for x in s._ws.sent] == [1024]
    await s.commit()
    assert len(s._ws.sent[1]) == 1024 and json.loads(s._ws.sent[2]) == {"type": "commit"}
    events = [e async for e in s.events()]
    assert events[0].text == "haan" and events[-1].type == "closed"


async def test_tts_stream_decodes_chunks(monkeypatch):
    pcm = b"\x01\x02" * 50
    msgs = [
        json.dumps({"type": "start"}),
        json.dumps({"type": "audio", "data": {"chunk_index": 0, "audio": base64.b64encode(pcm[:51]).decode()}}),
        json.dumps({"type": "audio", "data": {"chunk_index": 1, "audio": base64.b64encode(pcm[51:]).decode()}}),
        json.dumps({"type": "complete", "data": {"is_final": True}}),
    ]
    ws = FakeWS(msgs)

    class Ctx:
        async def __aenter__(self):
            return ws

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(tts_mod, "_ws_connect", lambda *a, **k: Ctx())
    out = b"".join([c async for c in tts_mod.tts_stream("KEY", "hello", voice="Lakshmi")])
    assert out == pcm
    assert json.loads(ws.sent[0])["text"] == "hello"


async def test_tts_stream_raises_on_error(monkeypatch):
    ws = FakeWS([json.dumps({"type": "error", "message": "bad voice"})])

    class Ctx:
        async def __aenter__(self):
            return ws

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(tts_mod, "_ws_connect", lambda *a, **k: Ctx())
    with pytest.raises(tts_mod.TtsError):
        _ = [c async for c in tts_mod.tts_stream("KEY", "hello", voice="X")]
