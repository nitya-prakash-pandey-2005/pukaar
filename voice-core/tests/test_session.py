"""VoiceAgentSession hardening: dead air, start-up failures, barge-in, echo, reconnects (offline fakes only)."""

import asyncio
import random

from voice_core.config import Settings
from voice_core.session import VoiceAgentSession
from voice_core.testing import FakeStt, ev, fake_tts
from voice_core.types import Turn


class StubAgent:
    """Minimal Agent: replies are scripted lists of sentences; a reply may be an Exception to raise."""

    user_label, agent_label = "caller", "agent"
    voice, tts_language, speed = "v", "hi-IN", 1.0
    stt_language_code, keyterms = "hi-IN", []

    def __init__(self, replies=None, *, greeting="", fillers=None, fallbacks=None, analyse=None):
        self.replies = list(replies or [])
        self._greeting = greeting
        self._fillers = list(fillers or [])
        if fallbacks is not None:
            self.fallback_texts = lambda: list(fallbacks)
        self.analyse = analyse
        self.recorded: list[Turn] = []
        self.analysed: list[int] = []
        self.ended = None

    def greeting(self):
        return self._greeting

    def filler_texts(self):
        return self._fillers

    def on_language(self, code):
        return None

    async def reply_sentences(self, history):
        r = self.replies.pop(0) if self.replies else []
        if isinstance(r, BaseException):
            raise r
        if callable(r):
            async for s in r():
                yield s
            return
        for s in r:
            await asyncio.sleep(0)
            yield s

    async def on_user_turn(self, history):
        self.analysed.append(len(history))
        if self.analyse:
            return await self.analyse(history)
        return None

    async def record(self, turn):
        self.recorded.append(turn)

    def end(self, secs):
        self.ended = secs


def make(agent, *, streams=None, factory=None, tts=fake_tts, filler_audio=None, delays=(0.01,), **kw):
    out_json, out_audio = [], []
    streams = list(streams or [])

    async def sj(m):
        out_json.append(m)

    async def sa(b):
        out_audio.append(b)

    sess = VoiceAgentSession(agent, send_json=sj, send_audio=sa, settings=Settings(sample_rate=8000),
                             stt_factory=factory or (lambda: streams.pop(0)), tts_fn=tts, rng=random.Random(0),
                             filler_audio=filler_audio, reconnect_delays=delays, **kw)
    return sess, out_json, out_audio


def turns(out_json, speaker):
    return [m for m in out_json if m.get("type") == "turn" and m.get("speaker") == speaker]


CLIP = b"\x00\x01" * 800  # 0.2 s at 8 kHz


# ---------------------------------------------------------------- 1. dead air when the LLM fails

async def test_llm_error_speaks_a_fallback_line():
    agent = StubAgent([RuntimeError("Groq 429")], fillers=["hmm", "ek minute"], fallbacks=["phir se bolo?"])
    stt = FakeStt([ev("transcript", "hello madam CBI se")], gap=0.01)
    sess, out_json, out_audio = make(agent, streams=[stt], filler_audio={"hmm": CLIP, "phir se bolo?": CLIP})
    await sess.start()
    await asyncio.sleep(0.1)
    await sess.wait_idle()
    said = [m["text"] for m in turns(out_json, "agent")]
    assert said == ["phir se bolo?"]
    assert CLIP in out_audio
    await sess.hangup()


async def test_empty_reply_falls_back_to_fillers_never_twice_in_a_row():
    agent = StubAgent([[], [], []], fillers=["a", "b", "not-rendered"])
    stt = FakeStt([ev("transcript", "pehli baat"), ev("transcript", "doosri baat"), ev("transcript", "teesri baat")],
                  gap=0.05)
    sess, out_json, _ = make(agent, streams=[stt], filler_audio={"a": CLIP, "b": CLIP})
    await sess.start()
    await asyncio.sleep(0.3)
    await sess.wait_idle()
    said = [m["text"] for m in turns(out_json, "agent")]
    assert len(said) == 3 and set(said) <= {"a", "b"}
    assert all(x != y for x, y in zip(said, said[1:]))
    await sess.hangup()


async def test_slow_first_sentence_times_out_into_fallback():
    async def hang():
        await asyncio.sleep(10)
        yield "too late"

    agent = StubAgent([hang], fillers=["hmm"])
    stt = FakeStt([ev("transcript", "hello ji")], gap=0.01)
    sess, out_json, _ = make(agent, streams=[stt], filler_audio={"hmm": CLIP}, first_sentence_timeout=0.1)
    await sess.start()
    await asyncio.sleep(0.4)
    await sess.wait_idle()
    assert [m["text"] for m in turns(out_json, "agent")] == ["hmm"]
    await sess.hangup()


async def test_no_fallback_when_reply_spoke_or_was_cancelled():
    agent = StubAgent([["theek hai."]], fillers=["hmm"])
    stt = FakeStt([ev("transcript", "hello ji")], gap=0.01)
    sess, out_json, _ = make(agent, streams=[stt], filler_audio={"hmm": CLIP})
    await sess.start()
    await asyncio.sleep(0.1)
    await sess.wait_idle()
    assert [m["text"] for m in turns(out_json, "agent")] == ["theek hai."]
    await sess.hangup()


# ---------------------------------------------------------------- 2. Prisma connect failure at call start

class FailingStt:
    connected = False

    async def connect(self):
        raise OSError("getaddrinfo failed (train tunnel)")


async def test_stt_connect_failure_at_start_still_greets_and_reconnects():
    agent = StubAgent([["achha."]], greeting="hello?")
    good = FakeStt([ev("transcript", "main bank se bol raha hoon")], gap=0.02)
    streams = [FailingStt(), good]
    sess, out_json, _ = make(agent, factory=lambda: streams.pop(0), delays=(0.01, 0.01))
    await sess.start()  # must not raise
    await asyncio.sleep(0.2)
    await sess.wait_idle()
    statuses = [m["stt"] for m in out_json if m.get("type") == "status"]
    assert statuses[0] == "reconnecting" and "connected" in statuses
    assert [m["text"] for m in turns(out_json, "agent")] == ["hello?", "achha."]
    assert [m["text"] for m in turns(out_json, "caller")] == ["main bank se bol raha hoon"]
    await sess.hangup()
    assert agent.ended is not None


async def test_stt_never_connects_reports_error_and_hangup_works():
    agent = StubAgent(greeting="hello?")
    sess, out_json, _ = make(agent, factory=FailingStt, delays=(0.01, 0.01))
    await sess.start()
    await asyncio.sleep(0.15)
    assert [m["stt"] for m in out_json if m.get("type") == "status"][-1] == "error"
    assert [m["text"] for m in turns(out_json, "agent")] == ["hello?"]
    await sess.hangup()
    assert agent.ended is not None


# ---------------------------------------------------------------- 3. a new transcript stops stale audio

async def slow_tts(*a, **k):  # 1.2 s of audio streamed in 0.3 s (faster than real time, like Timbre)
    for _ in range(6):
        await asyncio.sleep(0.05)
        yield b"\x00\x01" * 1600


async def test_new_transcript_stops_the_old_reply_audio():
    agent = StubAgent([["pehla jawab bahut lamba."], ["doosra jawab."]])
    stt = FakeStt([ev("transcript", "madam aapke naam pe FIR hai"),
                   ev("transcript", "aur abhi paise bhejne honge")], gap=0.2)
    sess, out_json, _ = make(agent, streams=[stt], tts=slow_tts)
    await sess.start()
    await asyncio.sleep(0.8)
    await sess.wait_idle()
    kinds = [m["type"] + (":" + m["speaker"] if m["type"] == "turn" else "") for m in out_json]
    second = [i for i, k in enumerate(kinds) if k == "turn:caller"][1]
    assert "stop_audio" in kinds[second:], kinds
    await sess.hangup()


async def test_transcript_does_not_cut_the_filler_it_triggered():
    agent = StubAgent([["achha."]], fillers=["hmm"])
    stt = FakeStt([ev("processing"), ev("transcript", "aapka KYC pending hai")], gap=0.1)
    sess, out_json, _ = make(agent, streams=[stt], filler_audio={"hmm": b"\x00\x01" * 8000}, filler_delay=0.01)
    await sess.start()
    await asyncio.sleep(0.4)
    await sess.wait_idle()
    assert not any(m["type"] == "stop_audio" for m in out_json)
    await sess.hangup()


# ---------------------------------------------------------------- 4. hang-up keeps the last turn's intel

async def test_hangup_waits_for_pending_analysis():
    done = []

    async def analyse(history):
        await asyncio.sleep(0.3)
        done.append(len(history))
        return {"type": "intel", "n": len(history)}

    agent = StubAgent([["achha."]], analyse=analyse)
    stt = FakeStt([ev("transcript", "UPI likhiye rathore.cbi@okaxis")], gap=0.01)
    sess, out_json, _ = make(agent, streams=[stt])
    await sess.start()
    await asyncio.sleep(0.05)
    await sess.hangup()
    assert done, "analysis was cancelled by hang-up"
    kinds = [m["type"] for m in out_json]
    assert kinds.index("intel") < kinds.index("session_ended")


async def test_hangup_does_not_wait_forever():
    async def analyse(history):
        await asyncio.sleep(30)

    agent = StubAgent([["achha."]], analyse=analyse)
    stt = FakeStt([ev("transcript", "hello ji kaun")], gap=0.01)
    sess, out_json, _ = make(agent, streams=[stt], hangup_grace=0.1)
    await sess.start()
    await asyncio.sleep(0.05)
    t = asyncio.get_running_loop().time()
    await sess.hangup()
    assert asyncio.get_running_loop().time() - t < 1.0


# ---------------------------------------------------------------- 5. speakerphone (half duplex)

LINE = "अरे बेटा, ज़रा धीरे बोलो, मैं लिख रही हूँ।"


async def test_half_duplex_own_echo_does_not_cut_the_agent_off():
    agent = StubAgent([[LINE], ["SECOND REPLY"]], fillers=["hmm"])
    stt = FakeStt([ev("transcript", "Madam main CBI se bol raha hoon"), ev("speech_start"), ev("processing"),
                   ev("transcript", "ज़रा धीरे बोलो मैं लिख रही हूं")], gap=0.15)
    sess, out_json, _ = make(agent, streams=[stt], tts=slow_tts, filler_audio={"hmm": CLIP}, half_duplex=True)
    await sess.start()
    await asyncio.sleep(0.9)
    await sess.wait_idle()
    assert not any(m["type"] == "stop_audio" for m in out_json)
    assert [m["text"] for m in turns(out_json, "agent")] == [LINE]
    await sess.hangup()


async def test_half_duplex_real_speech_still_barges_in():
    agent = StubAgent([[LINE], ["achha."]])
    stt = FakeStt([ev("transcript", "Madam main CBI se bol raha hoon"), ev("speech_start"),
                   ev("transcript", "aap abhi paise bhejiye warna arrest hoga")], gap=0.15)
    sess, out_json, _ = make(agent, streams=[stt], tts=slow_tts, half_duplex=True)
    await sess.start()
    await asyncio.sleep(0.9)
    await sess.wait_idle()
    kinds = [m["type"] for m in out_json]
    assert kinds.count("stop_audio") == 1
    assert [m["text"] for m in turns(out_json, "agent")] == [LINE, "achha."]
    await sess.hangup()


async def test_half_duplex_no_filler_from_the_echo_tail():
    agent = StubAgent(fillers=["hmm"])
    stt = FakeStt([ev("processing")], gap=0.05)
    sess, out_json, out_audio = make(agent, streams=[stt], filler_audio={"hmm": CLIP}, filler_delay=0.01,
                                     half_duplex=True)
    await sess.start()
    await sess._emit_audio(b"\x00\x00" * 400)  # 50 ms of agent speech: its echo tail lasts 800 ms more
    await asyncio.sleep(0.3)
    assert CLIP not in out_audio
    await sess.hangup()


async def test_full_duplex_speech_start_still_barges_in():
    agent = StubAgent([[LINE]])
    stt = FakeStt([ev("transcript", "Madam main CBI se bol raha hoon"), ev("speech_start")], gap=0.15)
    sess, out_json, _ = make(agent, streams=[stt], tts=slow_tts)
    await sess.start()
    await asyncio.sleep(0.5)
    await sess.wait_idle()
    assert any(m["type"] == "stop_audio" for m in out_json)
    await sess.hangup()


# ---------------------------------------------------------------- 6. analyses are coalesced, never queued

async def test_analysis_coalesces_while_one_is_running():
    seen = []

    async def analyse(history):
        seen.append(len([t for t in history if t.speaker == "caller"]))
        await asyncio.sleep(0.2)
        return {"type": "intel", "n": seen[-1]}

    agent = StubAgent([["a."], ["b."], ["c."], ["d."]], analyse=analyse)
    stt = FakeStt([ev("transcript", f"line number {i} hai ji") for i in range(4)], gap=0.02)
    sess, out_json, _ = make(agent, streams=[stt])
    await sess.start()
    await asyncio.sleep(0.15)
    await sess.wait_idle(timeout=2.0)
    await sess.hangup()
    assert seen[0] == 1 and seen[-1] == 4 and len(seen) == 2, seen


# ---------------------------------------------------------------- 7. reconnect storm

async def test_immediately_closing_stt_backs_off_then_reports_error():
    made = []

    def factory():
        made.append(FakeStt([], end="close"))
        return made[-1]

    sess, out_json, _ = make(StubAgent(), factory=factory, delays=(0.01, 0.02, 0.03))
    await sess.start()
    await asyncio.sleep(0.5)
    assert len(made) == 4, len(made)  # the first connect + one per delay, then stop
    statuses = [m["stt"] for m in out_json if m.get("type") == "status"]
    assert statuses[-1] == "error"
    await sess.hangup()


async def test_backoff_resets_after_a_stream_that_worked():
    made = []

    def factory():
        made.append(FakeStt([ev("transcript", f"baat number {len(made)} suniye")], gap=0.01, end="close"))
        return made[-1]

    agent = StubAgent([["achha."]] * 10)
    sess, out_json, _ = make(agent, factory=factory, delays=(0.01,))
    await sess.start()
    await asyncio.sleep(0.4)
    assert len(made) >= 3  # each stream produced a transcript, so each drop gets a fresh backoff
    await sess.hangup()


# ---------------------------------------------------------------- 10. fillers rendered after the call started

async def test_filler_dict_filled_later_reaches_a_running_session():
    shared: dict[str, bytes] = {}  # the app's warm-up fills this in place after the call has started
    agent = StubAgent(fillers=["hmm"])
    stt = FakeStt([ev("processing")], gap=0.05)
    sess, _, out_audio = make(agent, streams=[stt], filler_audio=shared, filler_delay=0.01)
    await sess.start()
    shared["hmm"] = CLIP
    await asyncio.sleep(0.2)
    assert CLIP in out_audio
    await sess.hangup()
