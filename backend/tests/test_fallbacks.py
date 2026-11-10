"""What callers, texters and dispatchers get when the LLM or Gnani fails, and the keyless fake mode itself."""

import json

from voice_core.config import Settings
from voice_core.testing import FakeLLM
from voice_core.types import Turn

from pukaar import assets
from pukaar.agent import PukaarAgent, dispatch_line
from pukaar.channels import relay_line, sms_intake
from pukaar.data import load_gazetteer, load_guidance
from pukaar.domain import Facts
from pukaar.fake_mode import FACTS, SCRIPT, FakeTriageLLM, ScriptedStt, tone_tts
from pukaar.guard import fallback
from pukaar.store import Store
from pukaar.triage import pick_guidance


class BrokenLLM(FakeLLM):
    """Answers the extraction prompt, then fails like a Groq 429 or timeout."""

    async def complete(self, messages, **kw):
        if self.replies:
            return self.replies.pop(0)
        raise RuntimeError("429 rate limited")


def _agent(store, llm, intel):
    return PukaarAgent(llm=llm, intel_llm=intel, store=store, places=load_gazetteer(), kb=load_guidance())


async def test_reply_llm_outage_speaks_the_safe_fallback_in_the_callers_language(tmp_path):
    store = Store(tmp_path / "p.db")
    a = _agent(store, BrokenLLM(), FakeLLM([json.dumps({"hazard": "fire", "locality": "Adyar"})]))
    a.on_language("hi-IN")
    out = [s async for s in a.reply_sentences([Turn("caller", "aag lagi hai Adyar mein", 1.0)])]
    assert " ".join(out) == fallback("hi-IN", "fire")  # no "stay high" advice for a fire
    assert a.asked == set()  # the question was not asked, so it will be asked next turn


async def test_sms_reply_llm_outage_still_pins_and_answers(tmp_path):
    store = Store(tmp_path / "p.db")
    llm = BrokenLLM([json.dumps({"hazard": "flood", "locality": "Velachery", "people_count": 3})])
    inc, reply = await sms_intake("Velachery flood 3 people on terrace", None, llm, store, load_gazetteer(),
                                  load_guidance())
    assert inc.facts.locality == "Velachery" and inc.loc_source == "landmark"
    assert reply == fallback("en-IN", "flood")


async def test_dispatch_line_falls_back_to_english_when_translation_fails():
    line = await dispatch_line(BrokenLLM(), "ta-IN", "NDRF boat 2", "20 minutes")
    assert line.startswith("A rescue team (NDRF boat 2) is on the way. Expected in 20 minutes.")


def test_unsupported_language_keeps_the_current_voice(tmp_path):
    a = _agent(Store(tmp_path / "p.db"), FakeLLM(), FakeLLM())
    assert a.on_language("xx-YY") is None and a.on_language(None) is None
    assert a.tts_language == "ta-IN"
    assert a.on_language("hi-IN")["language_name"] == "Hindi"
    assert a.filler_texts() == ["हाँ, मैं सुन रही हूँ।", "जी, बताइए।"]


def test_trapped_caller_gets_the_trapped_instruction_first():
    picked = pick_guidance(Facts(hazard="flood", trapped=True), load_guidance(), set())
    assert picked[0].id == "FLD-05" and len(picked) == 2


async def test_filler_render_failure_is_logged_not_raised(tmp_path, monkeypatch):
    async def boom(self, api_key, text, **kw):
        raise RuntimeError("429")

    monkeypatch.setattr(assets.TtsCache, "get_or_make", boom)
    assert await assets.load_or_make_fillers(Settings(cache_dir=tmp_path, gnani_api_key="k")) == {}


async def test_fillers_render_once_per_text(tmp_path, monkeypatch):
    calls = []

    async def ok(self, api_key, text, **kw):
        calls.append(text)
        return b"\x01\x00" * 10

    monkeypatch.setattr(assets.TtsCache, "get_or_make", ok)
    out = await assets.load_or_make_fillers(Settings(cache_dir=tmp_path, gnani_api_key="k"))
    assert set(out) == {t for t, _ in assets.filler_jobs()} and len(calls) == len(assets.filler_jobs())


# ---------------------------------------------------------------- fake mode (PUKAAR_FAKE=1)
async def test_fake_llm_follows_the_script_then_runs_dry():
    llm = FakeTriageLLM()
    extract = [{"role": "system", "content": "You extract facts ..."}, {"role": "user", "content": "x"}]
    got = [json.loads(await llm.complete(extract)) for _ in range(len(FACTS) + 1)]
    assert got == [*FACTS, {}]
    alert = json.loads(await llm.complete([{"role": "system", "content": "Translate this official alert"},
                                           {"role": "user", "content": "Move up"}]))
    assert alert["ta-IN"] == "Move up (ta-IN)"
    assert await llm.complete([{"role": "system", "content": "Translate into Tamil"},
                               {"role": "user", "content": "hello"}]) == "hello"


async def test_scripted_stt_speaks_the_first_line_then_closes():
    stt = ScriptedStt(every=0.01)
    await stt.connect()
    await stt.send_audio(b"\x00\x00")
    await stt.commit()
    kinds, text = [], None
    async for ev in stt.events():
        kinds.append(ev.type)
        if ev.type == "transcript":
            text = ev.text
            await stt.close()
    assert kinds[:4] == ["connected", "speech_start", "processing", "transcript"] and kinds[-1] == "closed"
    assert text == SCRIPT[0] and not stt.connected


async def test_tone_tts_length_follows_the_text_and_is_capped():
    short = b"".join([c async for c in tone_tts(None, "hi", sample_rate=8000)])
    long = b"".join([c async for c in tone_tts(None, "x" * 500, sample_rate=8000)])
    assert len(short) == int((0.05 * 2 + 0.4) * 8000) * 2
    assert len(long) == 4 * 8000 * 2  # capped at 4 s of PCM16


async def test_relay_sends_the_dispatchers_own_words_when_translation_fails():
    assert await relay_line(BrokenLLM(), "ta-IN", "Stay on the terrace, wave a torch") == "Stay on the terrace, wave a torch"


async def test_english_callers_get_the_dispatch_line_without_an_llm_call():
    llm = FakeLLM(["should not be used"])
    line = await dispatch_line(llm, "en-IN", "Fire tender 4", None)
    assert line == "A rescue team (Fire tender 4) is on the way. Stay where you are and keep this phone with you."
    assert llm.calls == []
