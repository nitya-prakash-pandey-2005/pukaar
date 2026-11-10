"""Gnani allows one short request at a time per key (live check, 8 Nov 2026: a second concurrent call got 429)."""

import asyncio
import base64
import json

import pytest

from voice_core.gnani import GnaniError, TtsError, gate, tts_stream
from voice_core.gnani import tts as tts_mod


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(gate, "RETRY_DELAYS", (0.0, 0.0, 0.0))


async def test_gate_serialises_concurrent_calls():
    active, peak = 0, 0

    async def req(i):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return i

    out = await asyncio.gather(*(gate.gnani_call(req, i) for i in range(4)))
    assert out == [0, 1, 2, 3] and peak == 1


async def test_retries_429_then_succeeds():
    calls = []

    async def req():
        calls.append(1)
        if len(calls) < 3:
            raise GnaniError(429, '{"error":"RATE_LIMITED"}')
        return "ok"

    assert await gate.gnani_call(req) == "ok" and len(calls) == 3


async def test_does_not_retry_client_errors():
    calls = []

    async def req():
        calls.append(1)
        raise GnaniError(400, "bad voice")

    with pytest.raises(GnaniError):
        await gate.gnani_call(req)
    assert len(calls) == 1


async def test_gives_up_after_all_retries():
    calls = []

    async def req():
        calls.append(1)
        raise GnaniError(503, "busy")

    with pytest.raises(GnaniError):
        await gate.gnani_call(req)
    assert len(calls) == len(gate.RETRY_DELAYS) + 1


async def test_stuck_holder_cannot_block_forever(monkeypatch):
    monkeypatch.setattr(gate, "GATE_TIMEOUT", 0.05)
    release = asyncio.Event()

    async def stuck():
        async with gate.gnani_slot():
            await release.wait()

    holder = asyncio.create_task(stuck())
    await asyncio.sleep(0.01)

    async def req():
        return "through"

    assert await asyncio.wait_for(gate.gnani_call(req), 1) == "through"
    release.set()
    await holder


def test_gate_works_across_event_loops():
    async def once():
        async def req():
            return 1

        return await gate.gnani_call(req)

    assert asyncio.run(once()) == 1 and asyncio.run(once()) == 1


def test_is_rate_limit():
    class Resp:
        status_code = 429

    class InvalidStatus(Exception):
        response = Resp()

    assert gate.is_rate_limit(GnaniError(429, "x")) and gate.is_rate_limit(InvalidStatus())
    assert gate.is_rate_limit(TtsError("Only 1 active request allowed"))
    assert not gate.is_rate_limit(GnaniError(401, "bad key")) and not gate.is_rate_limit(TtsError("bad voice"))


class _WS:
    def __init__(self, msgs):
        self.msgs = list(msgs)

    async def send(self, _):
        pass

    async def recv(self):
        await asyncio.sleep(0.01)
        return self.msgs.pop(0)


def _audio_msgs():
    pcm = base64.b64encode(b"\x01\x00" * 160).decode()
    return [json.dumps({"type": "audio", "data": {"audio": pcm}}), json.dumps({"type": "complete"})]


async def test_tts_stream_retries_rate_limit_before_first_chunk(monkeypatch):
    attempts = []

    class Ctx:
        async def __aenter__(self):
            attempts.append(1)
            if len(attempts) == 1:
                raise TtsError("RATE_LIMITED: only 1 active request")
            return _WS(_audio_msgs())

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(tts_mod, "_ws_connect", lambda *a, **k: Ctx())
    chunks = [c async for c in tts_stream("K", "haan", voice="Lakshmi")]
    assert len(attempts) == 2 and b"".join(chunks) == b"\x01\x00" * 160


async def test_tts_stream_holds_the_gate_while_streaming(monkeypatch):
    order = []

    class Ctx:
        async def __aenter__(self):
            return _WS(_audio_msgs())

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(tts_mod, "_ws_connect", lambda *a, **k: Ctx())

    async def stream():
        async for _ in tts_stream("K", "haan", voice="Lakshmi"):
            order.append("chunk")
        order.append("stream done")

    async def rest():
        await asyncio.sleep(0.005)  # starts while the stream is open

        async def req():
            order.append("rest")

        await gate.gnani_call(req)

    await asyncio.gather(stream(), rest())
    assert order == ["chunk", "stream done", "rest"]


async def test_abandoned_stream_releases_the_gate(monkeypatch):
    class Ctx:
        async def __aenter__(self):
            return _WS(_audio_msgs())

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(tts_mod, "_ws_connect", lambda *a, **k: Ctx())

    async def barge_in():
        async for _ in tts_stream("K", "haan", voice="Lakshmi"):
            await asyncio.sleep(10)  # cancelled mid-stream, like a barge-in

    t = asyncio.create_task(barge_in())
    await asyncio.sleep(0.05)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t

    async def req():
        return "free"

    assert await asyncio.wait_for(gate.gnani_call(req), 0.5) == "free"
