import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from voice_core.config import Settings
from voice_core.testing import FakeLLM

from pukaar.app import create_app
from pukaar.interpreter import (MAX_CLIP_BYTES, NOTE_ADDED, NOTE_FAILED, NOTE_LOST, FakeInterpLLM, FakeTranscriber,
                                Interpreter, check, clean, translate)

RESCUER_HI = "हम नाव लेकर आ रहे हैं। आपके घर के पास कौन सी बड़ी इमारत है?"
TO_CALLER_TA = "நாங்க படகுடன் வருகிறோம். உங்க வீட்டுக்கு பக்கத்துல எந்த பெரிய கட்டிடம் இருக்கு?"
CALLER_TA = "வேளச்சேரி பஸ் டிப்போ பக்கத்துல, 3வது மாடில 4 பேர் இருக்கோம்."
TO_RESCUER_HI = "हम वेलाचेरी बस डिपो के पास, 3 मंज़िल पर 4 लोग हैं।"


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def scripted(lines: dict[str, list[str]]):
    heard: list[tuple[str, str]] = []

    async def transcribe(wav: bytes, lang: str, role: str):
        heard.append((role, lang))
        return lines[role].pop(0), 150.0
    transcribe.heard = heard
    return transcribe


def speaker():
    said: list[tuple[str, str, str]] = []

    async def speak(text: str, lang: str, voice: str):
        said.append((text, lang, voice))
        return f"/api/interpret/audio/{len(said):040x}", 2.0
    speak.said = said
    return speak


def make(llm_replies, lines, clock=None, **langs):
    sp = speaker()
    tr = scripted(lines)
    it = Interpreter(transcribe=tr, llm=FakeLLM(llm_replies), speak=sp, clock=clock or Clock(), **langs)
    return it, tr, sp


# ---------------------------------------------------------------- both directions
def test_rescuer_hindi_to_caller_tamil():
    it, tr, sp = make([TO_CALLER_TA], {"rescuer": [RESCUER_HI]})
    assert it.claim("rescuer")["type"] == "floor"
    m = asyncio.run(it.turn("rescuer", b"wav"))
    assert tr.heard == [("rescuer", "hi-IN")]  # Prisma gets ONE locale: the speaker's
    assert m["original"] == RESCUER_HI and m["translation"] == TO_CALLER_TA and m["translated"] and m["note"] is None
    assert (m["src_lang"], m["dst_lang"], m["spoken_lang"]) == ("hi-IN", "ta-IN", "ta-IN")
    assert sp.said == [(TO_CALLER_TA, "ta-IN", "Chetana")]
    assert m["prisma_ms"] == 150 and {"stt_ms", "translate_ms", "tts_ms", "total_ms", "audio_url"} <= m.keys()
    assert it.speaking is None  # floor given back


def test_caller_tamil_back_to_rescuer_hindi_keeps_numbers_and_place():
    it, tr, sp = make([TO_RESCUER_HI], {"caller": [CALLER_TA]})
    it.claim("caller")
    m = asyncio.run(it.turn("caller", b"wav"))
    assert m["translation"] == TO_RESCUER_HI and m["translated"]
    assert "3" in m["translation"] and "4" in m["translation"] and "वेलाचेरी" in m["translation"]
    assert sp.said == [(TO_RESCUER_HI, "hi-IN", "Prakash")]


def test_english_rescuer_telugu_caller():
    it, _, sp = make(["మేము పడవతో వస్తున్నాం."], {"rescuer": ["We are coming with a boat."]},
                     rescuer_lang="en-IN", caller_lang="te-IN")
    it.claim("rescuer")
    m = asyncio.run(it.turn("rescuer", b"wav"))
    assert m["dst_lang"] == "te-IN" and sp.said[0][1] == "te-IN"
    prompt = it.llm.calls[0][0]["content"]
    assert "from English into Telugu" in prompt and "number" in prompt and "Never add" in prompt


def test_same_language_needs_no_llm_call():
    it, _, sp = make([], {"rescuer": ["हम आ रहे हैं।"]}, caller_lang="hi-IN")
    it.claim("rescuer")
    m = asyncio.run(it.turn("rescuer", b"wav"))
    assert m["translation"] == "हम आ रहे हैं।" and it.llm.calls == [] and m["translated"]


# ---------------------------------------------------------------- the guard on translations
@pytest.mark.parametrize("src,out,note", [
    ("हम नाव लेकर आ रहे हैं।", "நாங்க 10 நிமிடத்தில் வருவோம்.", NOTE_ADDED),  # a time the rescuer never gave
    ("हम नाव लेकर आ रहे हैं।", "நாங்க வருகிறோம், நீங்க பாதுகாப்பாக இருக்கிறீர்கள்.", NOTE_ADDED),  # "you are safe"
    ("We are coming with a boat.", "हम 2 नाव लेकर आ रहे हैं।", NOTE_ADDED),  # an invented number
    ("We have 3 boats.", "எங்களிடம் படகுகள் உள்ளன.", NOTE_LOST),  # a number dropped
    ("Team reaches in 20 minutes.", "टीम 20 मिनट में पहुँचेगी।", None),  # the rescuer's own time survives
])
def test_check(src, out, note):
    assert check(src, out) == note


def test_guard_fallback_speaks_original_words_with_note():
    it, _, sp = make(["நாங்க 10 நிமிடத்தில் வருவோம், நீங்க பாதுகாப்பாக இருக்கிறீர்கள்."], {"rescuer": [RESCUER_HI]})
    it.claim("rescuer")
    m = asyncio.run(it.turn("rescuer", b"wav"))
    assert m["translation"] == RESCUER_HI and not m["translated"] and m["note"] == NOTE_ADDED
    assert sp.said == [(RESCUER_HI, "hi-IN", "Chetana")]  # pronounced as Hindi, not as Tamil


def test_llm_failure_or_empty_falls_back():
    class Boom:
        async def complete(self, *a, **k):
            raise RuntimeError("groq 429")
    assert asyncio.run(translate(Boom(), "हम आ रहे हैं", "hi-IN", "ta-IN")) == ("हम आ रहे हैं", NOTE_FAILED)
    assert asyncio.run(translate(FakeLLM([""]), "हम आ रहे हैं", "hi-IN", "ta-IN")) == ("हम आ रहे हैं", NOTE_FAILED)


def test_clean_strips_think_and_labels():
    assert clean("<think>hmm</think>\nTranslation: \"நாங்க வருகிறோம்\"") == "நாங்க வருகிறோம்"


def test_unheard_turn_is_not_translated():
    it, _, sp = make([], {"caller": ["  "]})
    it.claim("caller")
    m = asyncio.run(it.turn("caller", b"wav"))
    assert m["type"] == "unheard" and sp.said == [] and it.speaking is None


# ---------------------------------------------------------------- turn-taking
def test_speaking_lock_and_barge_in():
    clock = Clock()
    it, _, _ = make([TO_CALLER_TA], {"rescuer": [RESCUER_HI]}, clock=clock)
    assert it.claim("rescuer")["type"] == "floor"
    assert it.claim("caller") == {"type": "busy", "role": "caller", "speaking": "rescuer"}  # no overlap
    asyncio.run(it.turn("rescuer", b"wav"))  # 2 s of Tamil audio now plays to the caller
    clock.t += 1.0
    res = it.claim("caller")  # the caller answers before it ends: barge-in
    assert res["type"] == "floor" and res["barge_in"] and res["stop_audio_of"] == "rescuer"
    it.release("caller")
    clock.t += 5.0
    assert it.claim("rescuer")["barge_in"] is False


def test_turn_without_floor_is_refused():
    it, _, _ = make([], {"caller": ["x"]})
    with pytest.raises(ValueError):
        asyncio.run(it.turn("caller", b"wav"))


@pytest.mark.parametrize("langs", [{"rescuer_lang": "ta-IN"}, {"caller_lang": "fr-FR"}, {"caller_lang": "kn-IN"}])
def test_language_validation(langs):
    with pytest.raises(ValueError):
        make([], {}, **langs)


def test_unknown_role():
    it, _, _ = make([], {})
    with pytest.raises(ValueError):
        it.claim("dispatcher")
    with pytest.raises(ValueError):
        it.set_lang("dispatcher", "hi-IN")


# ---------------------------------------------------------------- WebSocket end to end
@pytest.fixture
def client(tmp_path):
    settings = Settings(sample_rate=8000, cache_dir=tmp_path / "cache")
    made = {}

    def factory(rescuer_lang, caller_lang):
        sp = speaker()
        it = Interpreter(transcribe=scripted({"rescuer": [RESCUER_HI], "caller": [CALLER_TA]}),
                         llm=FakeLLM([TO_CALLER_TA, TO_RESCUER_HI]), speak=sp,
                         rescuer_lang=rescuer_lang, caller_lang=caller_lang)
        made["it"], made["sp"] = it, sp
        return it

    with TestClient(create_app(settings, interpreter_factory=factory, intel_llm=FakeLLM([]))) as c:
        c.made = made
        yield c


def _until(ws, type_, n=20):
    for _ in range(n):
        m = ws.receive_json()
        if m.get("type") == type_:
            return m
    raise AssertionError(f"no {type_}")


SECOND = b"\x00\x01" * 16000  # 1 s of 16 kHz PCM16


def test_ws_both_directions(client):
    with client.websocket_connect("/ws/interpret") as ws:
        ws.send_json({"type": "start", "rescuer_lang": "hi-IN", "caller_lang": "ta-IN"})
        ready = ws.receive_json()
        assert ready["type"] == "ready" and ready["machine_interpretation"] is True
        assert ready["langs"] == {"rescuer": "hi-IN", "caller": "ta-IN"} and ready["voices"]["caller"] == "Chetana"

        ws.send_json({"type": "talk", "role": "rescuer"})
        assert ws.receive_json()["type"] == "floor"
        ws.send_json({"type": "talk", "role": "caller"})  # the other side cannot talk over the rescuer
        assert ws.receive_json() == {"type": "busy", "role": "caller", "speaking": "rescuer"}
        ws.send_bytes(SECOND)
        ws.send_json({"type": "done", "role": "rescuer"})
        assert ws.receive_json() == {"type": "interpreting", "role": "rescuer"}
        t1 = _until(ws, "turn")
        assert (t1["original"], t1["translation"], t1["dst_lang"]) == (RESCUER_HI, TO_CALLER_TA, "ta-IN")
        assert _until(ws, "floor_free")

        ws.send_json({"type": "talk", "role": "caller"})  # answers while the Tamil audio still plays
        floor = ws.receive_json()
        assert floor["type"] == "floor" and floor["barge_in"] and floor["stop_audio_of"] == "rescuer"
        ws.send_bytes(SECOND)
        ws.send_json({"type": "done", "role": "caller"})
        t2 = _until(ws, "turn")
        assert t2["role"] == "caller" and t2["translation"] == TO_RESCUER_HI and t2["spoken_lang"] == "hi-IN"
        assert client.made["sp"].said[1] == (TO_RESCUER_HI, "hi-IN", "Prakash")
        ws.send_json({"type": "hangup"})


def test_ws_language_validation(client):
    with client.websocket_connect("/ws/interpret") as ws:
        ws.send_json({"type": "start", "rescuer_lang": "hi-IN", "caller_lang": "xx-IN"})
        assert ws.receive_json()["type"] == "error"
    with client.websocket_connect("/ws/interpret") as ws:
        ws.send_json({"type": "start"})
        assert ws.receive_json()["langs"] == {"rescuer": "hi-IN", "caller": "ta-IN"}
        ws.send_json({"type": "set_lang", "role": "caller", "lang": "te-IN"})
        assert ws.receive_json()["langs"]["caller"] == "te-IN"
        ws.send_json({"type": "set_lang", "role": "rescuer", "lang": "ta-IN"})
        assert "rescuer language must be one of" in ws.receive_json()["error"]


def test_ws_mis_tap_is_not_sent_to_prisma(client):
    with client.websocket_connect("/ws/interpret") as ws:
        ws.send_json({"type": "start"})
        ws.receive_json()
        ws.send_json({"type": "talk", "role": "caller"})
        ws.receive_json()
        ws.send_bytes(b"\x00\x01" * 100)
        ws.send_json({"type": "done", "role": "caller"})
        assert ws.receive_json()["reason"] == "too short"
        assert ws.receive_json()["type"] == "floor_free"
        assert client.made["sp"].said == []


def test_ws_bad_first_message_closes(client):
    with client.websocket_connect("/ws/interpret") as ws:
        ws.send_json({"type": "talk", "role": "rescuer"})
        assert ws.receive_json()["type"] == "error"


def test_fake_mode_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("PUKAAR_FAKE", "1")
    with TestClient(create_app(Settings(sample_rate=8000, cache_dir=tmp_path / "c"))) as c:
        with c.websocket_connect("/ws/interpret") as ws:
            ws.send_json({"type": "start", "sample_rate": 16000})
            ws.receive_json()
            ws.send_json({"type": "talk", "role": "rescuer"})
            ws.receive_json()
            ws.send_bytes(SECOND)
            ws.send_json({"type": "done", "role": "rescuer"})
            t = _until(ws, "turn")
            assert t["translated"] and t["translation"] != t["original"]
            r = c.get(t["audio_url"])
            assert r.status_code == 200 and r.content[:4] == b"RIFF" and r.headers["content-type"] == "audio/wav"
        assert c.get("/api/interpret/audio/" + "0" * 40).status_code == 404
        assert c.get("/api/interpret/audio/../../x").status_code == 404


def test_fake_parts_cycle():
    tr = FakeTranscriber()
    a = asyncio.run(tr(b"", "hi-IN", "rescuer"))[0]
    assert asyncio.run(FakeInterpLLM().complete([{"role": "user", "content": a}])) != a
    assert json.dumps(a, ensure_ascii=False)


def test_ws_cancel_frees_the_floor_and_long_clips_are_capped(client):
    with client.websocket_connect("/ws/interpret") as ws:
        ws.send_json({"type": "start"})
        ws.receive_json()
        ws.send_json({"type": "talk", "role": "rescuer"})
        ws.receive_json()
        ws.send_json({"type": "cancel", "role": "rescuer"})
        assert ws.receive_json()["type"] == "floor_free"
        ws.send_json({"type": "talk", "role": "caller"})  # the other side can talk now
        assert ws.receive_json()["type"] == "floor"
        got = []
        client.made["it"].transcribe = lambda wav, lang, role: _record(got, wav)
        for _ in range(35):  # 35 s held down: Prisma REST gets at most 30 s
            ws.send_bytes(SECOND)
        ws.send_json({"type": "done", "role": "caller"})
        _until(ws, "unheard")
        assert len(got[0]) - 44 == MAX_CLIP_BYTES


async def _record(got, wav):
    got.append(wav)
    return "", None


def test_ws_only_the_floor_holder_can_end_or_cancel_a_turn(client):
    with client.websocket_connect("/ws/interpret") as ws:
        ws.send_json({"type": "start"})
        ws.receive_json()
        ws.send_json({"type": "talk", "role": "rescuer"})
        ws.receive_json()
        ws.send_bytes(SECOND)
        for msg in ({"type": "cancel", "role": "caller"}, {"type": "cancel"}, {"type": "done"},
                    {"type": "done", "role": "caller"}):
            ws.send_json(msg)  # all ignored: the rescuer's clip is kept
        ws.send_json({"type": "done", "role": "rescuer"})
        assert ws.receive_json() == {"type": "interpreting", "role": "rescuer"}
        assert _until(ws, "turn")["original"] == RESCUER_HI
