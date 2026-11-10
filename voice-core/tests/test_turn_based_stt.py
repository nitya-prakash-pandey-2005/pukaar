"""Turn-based STT fallback (energy VAD + Prisma REST), the echo/silence guards and the Prisma REST client.
No network: transcribe_rest is replaced by a fake, and the REST client is driven through httpx.MockTransport."""

import asyncio
import json

import httpx
import numpy as np
import pytest

from voice_core import turns
from voice_core.gnani import GnaniError, gate, stt_rest
from voice_core.gnani.stt_stream import SttEvent
from voice_core.turns import TurnBasedStt, is_echo, is_meaningful, split_sentences

SR = 8000


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(gate, "RETRY_DELAYS", (0.0, 0.0, 0.0))


def chunk(ms: int, amp: float) -> bytes:
    """`ms` of a 300 Hz tone at amplitude `amp` (0 = silence) as PCM16 mono."""
    n = SR * ms // 1000
    x = amp * np.sin(2 * np.pi * 300 * np.arange(n) / SR)
    return (x * 32767).astype("<i2").tobytes()


async def drain(stt: TurnBasedStt, n: int, timeout: float = 2.0) -> list[SttEvent]:
    out: list[SttEvent] = []

    async def take():
        async for e in stt.events():
            out.append(e)
            if len(out) == n:
                return

    await asyncio.wait_for(take(), timeout)
    return out


@pytest.fixture
def rest_calls(monkeypatch):
    """Replace the Prisma REST call; records (wav, kwargs) and answers with a transcript."""
    calls: list[tuple[bytes, dict]] = []

    async def fake(api_key, wav, **kw):
        calls.append((wav, kw))
        return SttEvent("transcript", text="namaste beta", language="hi-IN", latency_ms=120.0)

    monkeypatch.setattr(turns, "transcribe_rest", fake)
    return calls


async def test_vad_opens_on_speech_and_sends_one_utterance_after_silence(rest_calls):
    stt = TurnBasedStt("k", sample_rate=SR, start_ms=200, end_ms=600, keyterms=["UPI"])
    await stt.connect()
    for _ in range(10):  # 1 s of quiet room: nothing happens, pre-roll stays capped at 400 ms
        await stt.send_audio(chunk(100, 0.0))
    assert len(stt._buf) <= SR * 2 * 0.4 and not stt._speaking
    for _ in range(5):  # 500 ms of speech
        await stt.send_audio(chunk(100, 0.3))
    assert stt._speaking
    for _ in range(6):  # 600 ms of silence closes the utterance
        await stt.send_audio(chunk(100, 0.0))
    events = await drain(stt, 4)
    assert [e.type for e in events] == ["connected", "speech_start", "processing", "transcript"]
    assert events[-1].text == "namaste beta"
    assert len(rest_calls) == 1
    wav, kw = rest_calls[0]
    assert wav[:4] == b"RIFF" and kw["keyterms"] == ["UPI"] and kw["language_code"] == "hi-IN,en-IN"
    assert not stt._speaking and not stt._buf


async def test_short_blip_does_not_start_an_utterance(rest_calls):
    stt = TurnBasedStt("k", sample_rate=SR, start_ms=200)
    await stt.send_audio(chunk(100, 0.3))  # 100 ms click, then quiet: voiced time resets
    await stt.send_audio(chunk(100, 0.0))
    await stt.send_audio(chunk(100, 0.3))
    assert not stt._speaking and stt._q.empty() and not rest_calls


async def test_empty_audio_is_ignored(rest_calls):
    stt = TurnBasedStt("k", sample_rate=SR)
    await stt.send_audio(b"")
    assert stt._q.empty() and not stt._buf


async def test_long_monologue_is_cut_at_max_s(rest_calls):
    stt = TurnBasedStt("k", sample_rate=SR, start_ms=100, max_s=1.0)
    for _ in range(11):  # non-stop speech: the utterance is cut once it passes 1.0 s
        await stt.send_audio(chunk(100, 0.3))
    events = await drain(stt, 3)
    assert [e.type for e in events] == ["speech_start", "processing", "transcript"]
    assert len(rest_calls) == 1 and not stt._speaking
    assert len(rest_calls[0][0]) - 44 == SR * 2 * 11 // 10  # the whole 1.1 s went out (44-byte WAV header)


async def test_commit_flushes_an_open_utterance_and_close_ends_events(rest_calls):
    stt = TurnBasedStt("k", sample_rate=SR, start_ms=100)
    await stt.commit()  # nothing open: no-op
    assert stt._q.empty()
    for _ in range(3):
        await stt.send_audio(chunk(100, 0.3))
    await stt.commit()
    got = await drain(stt, 3)
    assert [e.type for e in got] == ["speech_start", "processing", "transcript"]
    await stt.close()
    assert not stt.connected
    assert [e.type async for e in stt.events()] == ["closed"]


async def test_rest_failure_becomes_an_error_event_not_a_crash(monkeypatch):
    async def boom(api_key, wav, **kw):
        raise GnaniError(400, "bad audio")

    monkeypatch.setattr(turns, "transcribe_rest", boom)
    stt = TurnBasedStt("k", sample_rate=SR, start_ms=100)
    for _ in range(3):
        await stt.send_audio(chunk(100, 0.3))
    await stt.commit()
    events = await drain(stt, 3)
    assert events[-1].type == "error" and "bad audio" in events[-1].raw["message"]
    assert not stt.busy.locked()


async def test_only_one_rest_request_in_flight(monkeypatch):
    active, peak = 0, 0

    async def slow(api_key, wav, **kw):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        return SttEvent("transcript", text="haan")

    monkeypatch.setattr(turns, "transcribe_rest", slow)
    stt = TurnBasedStt("k", sample_rate=SR, start_ms=100)
    for _ in range(2):  # two utterances back to back
        for _ in range(2):
            await stt.send_audio(chunk(100, 0.3))
        await stt.commit()
    events = await drain(stt, 6)
    assert [e.type for e in events].count("transcript") == 2 and peak == 1


# -- echo / silence guards ------------------------------------------------------------------------------------------


def test_is_meaningful_ignores_punctuation_and_single_characters():
    assert not is_meaningful("")
    assert not is_meaningful(" ... ")
    assert not is_meaningful("a.")
    assert is_meaningful("haan")


def test_is_echo_matches_spelling_variants_and_ignores_unrelated_speech():
    said = ["अरे बेटा, ज़रा रुको, चश्मा ढूँढ रही हूँ।"]
    assert is_echo("अरे बेटा जरा रुको चश्मा ढूंढ रही हूं", said)  # nukta and chandrabindu differences
    assert not is_echo("aapka account block ho jayega", said)
    assert not is_echo("", said)
    assert not is_echo("kuch bhi", ["", "  "])


def test_is_echo_containment_rules():
    # the transcript (3+ words) is part of what Dadi said
    assert is_echo("bank wale aaye the", ["Kal bank wale aaye the, unhone kuch nahi bataya beta."])
    # a short Dadi line inside a long scammer sentence is not an echo of it
    assert not is_echo("accha ab jaldi se OTP batao mujhe", ["Accha."])


def test_is_echo_spanning_several_lines():
    said = ["Haan beta, ruko zara.", "Mera chashma kahan gaya?", "Pota abhi school gaya hai."]
    assert is_echo("ruko zara mera chashma kahan gaya pota abhi", said)


def test_split_sentences_merges_tiny_pieces_forward():
    sents, rest = split_sentences("a\nTheek hai. Aur", final=False)
    assert sents == ["a Theek hai."] and rest == "Aur"
    assert split_sentences("pehla\nदूसरा। ", final=False) == (["pehla", "दूसरा।"], "")


# -- Prisma REST client (no network) --------------------------------------------------------------------------------


async def test_transcribe_rest_sends_the_documented_form_and_parses_the_reply():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"], seen["key"], seen["body"] = str(req.url), req.headers["X-API-Key-ID"], req.content
        return httpx.Response(200, json={"transcript": "  namaste  ", "detected_language_code": "hi-IN",
                                         "end_to_end_latency": 0.42})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        ev = await stt_rest.transcribe_rest("key-1", b"RIFFwav", keyterms=["पेटीएम"], client=client)
    assert ev.type == "transcript" and ev.text == "namaste" and ev.language == "hi-IN"
    assert ev.latency_ms == pytest.approx(420.0)
    assert seen["url"] == stt_rest.STT_REST_URL and seen["key"] == "key-1"
    body = seen["body"].decode("utf-8")
    assert 'name="model"' in body and "prisma-v3.0" in body and 'name="format"' in body and "codemix" in body
    assert json.dumps(["पेटीएम"], ensure_ascii=False) in body and 'filename="clip.wav"' in body


async def test_transcribe_rest_handles_missing_fields():
    def handler(req):
        return httpx.Response(200, json={"transcript": None, "end_to_end_latency": "n/a"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        ev = await stt_rest.transcribe_rest("k", b"x", client=client)
    assert ev.text == "" and ev.language is None and ev.latency_ms is None


async def test_transcribe_rest_retries_429_then_raises_on_client_error():
    statuses = iter([429, 200])

    def handler(req):
        code = next(statuses)
        return httpx.Response(code, json={"transcript": "ok"} if code == 200 else {"error": "RATE_LIMITED"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (await stt_rest.transcribe_rest("k", b"x", client=client)).text == "ok"

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401, text="no key"))) as c:
        with pytest.raises(GnaniError) as exc:
            await stt_rest.transcribe_rest("k", b"x", client=c)
    assert exc.value.status == 401
