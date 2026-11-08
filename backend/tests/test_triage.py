import json

from voice_core.testing import FakeLLM
from voice_core.types import Turn

from pukaar.data import load_guidance
from pukaar.domain import Facts
from pukaar.guard import FALLBACK, guard_reply
from pukaar.triage import build_reply_messages, extract_facts, pick_guidance

HIST = [Turn("caller", "Velachery la irukom, thanni chest varaikkum, paati insulin podanum", 1.0)]


async def test_extract_facts_parses_and_drops_invalid():
    llm = FakeLLM([json.dumps({"locality": "Velachery", "water_level": "chest", "medical_needs": ["insulin", "magic"],
                               "vulnerable": ["elderly"], "people_count": "4", "hazard": "tsunami", "lat": 1.0})])
    f = await extract_facts(llm, HIST, Facts())
    assert f.locality == "Velachery" and f.water_level == "chest" and f.people_count == 4
    assert f.medical_needs == ["insulin"] and f.hazard is None and f.lat is None


async def test_extract_facts_bad_json_keeps_previous():
    prev = Facts(locality="Tambaram")
    assert await extract_facts(FakeLLM(["sorry, I can't"]), HIST, prev) == prev
    assert await extract_facts(FakeLLM(['{"people_count": "many"}']), HIST, prev) == prev

    class Boom:
        async def complete(self, *a, **k):
            raise RuntimeError("network")
    assert await extract_facts(Boom(), HIST, prev) == prev


def test_pick_guidance_specific_first():
    kb = load_guidance()
    f = Facts(hazard="flood", water_level="chest", medical_needs=["insulin"])
    assert [g.id for g in pick_guidance(f, kb, set())] == ["FLD-01", "MED-02"]
    assert [g.id for g in pick_guidance(f, kb, {"FLD-01"})] == ["MED-02", "FLD-03"]
    assert [g.id for g in pick_guidance(Facts(hazard="fire"), kb, set())] == ["FIR-01", "GEN-01"]


def test_build_reply_messages():
    kb = load_guidance()
    msgs = build_reply_messages(Facts(locality="Velachery"), "people", kb[:1], "ta-IN", None, HIST)
    sys = msgs[0]["content"]
    assert msgs[0]["role"] == "system" and "Tamil" in sys and "[[FLD-01]]" in sys and "none" in sys
    assert "how many people" in sys and msgs[-1] == {"role": "user", "content": HIST[0].text}
    assert "Do NOT say they are safe" in sys and "Never write an id without saying the instruction" in sys


def test_extract_prompt_forbids_default_facts():
    from pukaar.triage import EXTRACT_PROMPT
    assert "Never guess or fill defaults" in EXTRACT_PROMPT and 'water_level "none" only if' in EXTRACT_PROMPT


def test_guard_reply():
    assert guard_reply("Stay up high [[FLD-01]]", {"FLD-01"}, None) == ("Stay up high", ["FLD-01"])
    assert guard_reply("Do this [[XYZ-99]]", {"FLD-01"}, None) == (FALLBACK["en"], [])
    assert guard_reply("The boat will reach in 10 minutes.", set(), None) == (FALLBACK["en"], [])
    assert guard_reply("The boat will reach in 10 minutes.", set(), "20 min") == ("The boat will reach in 10 minutes.", [])
    assert guard_reply("படகு 10 நிமிடத்தில் வரும்", set(), None, "ta-IN") == (FALLBACK["ta"], [])
    assert guard_reply("Boat jaldi pahunch jayegi", set(), None, "hi-IN")[0] == FALLBACK["hi"]


def test_guard_blocks_time_promises_in_words_hours_and_telugu():
    for text, lang in [
        ("The boat will reach you in ten minutes.", "en"),
        ("Rescuers will be there within an hour.", "en"),
        ("Help will come in 2 hours.", "en"),
        ("Boat aadhe ghante mein aa jayegi.", "hi"),
        ("नाव आधे घंटे में पहुंचेगी।", "hi"),
        ("படகு ஒரு மணி நேரத்தில் வரும்.", "ta"),
        ("పడవ 10 నిమిషాల్లో వస్తుంది.", "te"),
        ("పడవ ఒక గంటలో వస్తుంది.", "te"),
    ]:
        assert guard_reply(text, set(), None, lang)[0] == FALLBACK[lang], text
    assert guard_reply("The boat will reach you in ten minutes.", set(), "10 min")[0].startswith("The boat")


def test_guard_blocks_false_reassurance():
    for text, lang in [("Don't worry, you are safe now.", "en"), ("You'll be fine, stay there.", "en"),
                       ("घबराइए मत, आप सुरक्षित हैं।", "hi"), ("Aap safe hain, ghabraiye mat.", "hi"),
                       ("பயப்படாதீங்க, நீங்க பாதுகாப்பா இருக்கீங்க.", "ta"), ("మీరు సురక్షితంగా ఉన్నారు.", "te")]:
        assert guard_reply(text, set(), "20 min", lang)[0] == FALLBACK[lang], text


def test_guard_keeps_every_approved_line_and_plain_questions():
    for g in load_guidance():
        assert guard_reply(f"Stay calm. {g.text_en} [[{g.id}]]", {g.id}, None)[1] == [g.id], g.id
    for line in FALLBACK.values():
        assert guard_reply(line, set(), None)[0] == line
    for ok in ["I am with you. How high is the water on your body?", "Stay calm. How many people are with you?",
               "Stay safe and keep this phone with you.", "Tell me the area name and a nearby landmark."]:
        assert guard_reply(ok, set(), None)[0] == ok
