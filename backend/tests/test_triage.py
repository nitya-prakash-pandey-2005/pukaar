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
