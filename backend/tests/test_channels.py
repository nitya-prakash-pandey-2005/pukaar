import json
import xml.etree.ElementTree as ET

from voice_core.testing import FakeLLM

from pukaar.channels import CAP_NS, cap_xml, detect_lang, relay_line, sms_intake
from pukaar.data import load_gazetteer, load_guidance
from pukaar.store import Store

SMS = "வேளச்சேரி ல மாடி மேல நாலு பேர் இருக்கோம், தண்ணி நெஞ்சு வரைக்கும் வந்துடுச்சு"


def test_detect_lang_by_script():
    assert detect_lang(SMS) == "ta-IN" and detect_lang("पानी घर में आ गया") == "hi-IN"
    assert detect_lang("నీళ్ళు ఇంట్లోకి") == "te-IN" and detect_lang("water inside house") == "en-IN"


async def test_sms_intake_creates_text_incident_and_guarded_reply(tmp_path):
    store = Store(tmp_path / "p.db")
    llm = FakeLLM([
        json.dumps({"locality": "Velachery", "people_count": 4, "on_roof": True, "water_level": "chest", "hazard": "flood"}),
        "பயப்படாதீங்க, உங்க செய்தி கிடைச்சுது. 10 நிமிஷத்துல வருவோம்.",  # invented ETA -> guard replaces it
    ])
    inc, reply = await sms_intake(SMS, None, llm, store, load_gazetteer(), load_guidance())
    assert inc.channel == "text" and inc.facts.people_count == 4 and inc.lat is not None
    assert "10 நிமிஷ" not in reply and reply
    assert store.call_lang(inc.call_ids[0]) == "ta-IN"


async def test_relay_line_translates_and_keeps_english():
    assert await relay_line(FakeLLM([]), "en-IN", "Boat is at the temple.") == "Boat is at the temple."
    assert await relay_line(FakeLLM(["படகு கோயிலில் உள்ளது."]), "ta-IN", "Boat is at the temple.") == "படகு கோயிலில் உள்ளது."
    assert await relay_line(FakeLLM([]), "ta-IN", "Boat is at the temple.") == "Boat is at the temple."  # LLM down


def test_cap_xml_has_one_info_block_per_language():
    xml = cap_xml("Adyar river is rising. Move to the relief camp.",
                  [{"lang": "en-IN", "text": "Adyar river is rising."}, {"lang": "ta-IN", "text": "அடையாறு ஆறு உயர்கிறது."}],
                  area="Chennai", identifier="pukaar-1", sent="2026-11-08T20:00:00+05:30")
    root = ET.fromstring(xml)
    ns = {"c": CAP_NS}
    assert root.find("c:identifier", ns).text == "pukaar-1" and root.find("c:status", ns).text == "Exercise"
    infos = root.findall("c:info", ns)
    assert [i.find("c:language", ns).text for i in infos] == ["en-IN", "ta-IN"]
    assert infos[1].find("c:description", ns).text == "அடையாறு ஆறு உயர்கிறது."
    assert infos[0].find("c:area/c:areaDesc", ns).text == "Chennai"


async def test_relay_never_adds_a_time_promise_reassurance_or_number():
    src = "The boat is at the temple gate. Wave a white cloth."
    # a translation that adds facts is not sent: the dispatcher's own English words go instead
    assert await relay_line(FakeLLM(["படகு 10 நிமிஷத்துல வந்துடும்."]), "ta-IN", src) == src
    assert await relay_line(FakeLLM(["नाव मंदिर के द्वार पर है। आप अब सुरक्षित हैं।"]), "hi-IN", src) == src
    assert await relay_line(FakeLLM(["படகு 2 கோவில் வாயிலில் உள்ளது."]), "ta-IN", src) == src


async def test_relay_keeps_the_dispatchers_own_time_and_numbers():
    src = "Boat 2 reaches the temple in 20 minutes."
    out = "படகு 2, 20 நிமிடங்களில் கோவிலை அடையும்."
    assert await relay_line(FakeLLM([out]), "ta-IN", src) == out
    assert await relay_line(FakeLLM(["படகு 2, 30 நிமிடங்களில் கோவிலை அடையும்."]), "ta-IN", src) == src  # changed number


async def test_unlocated_sms_is_not_told_the_control_room_sees_them(tmp_path):
    # GEN-01 = "the control room can see you on the map": false with no GPS and no known place (as for voice calls)
    facts = json.dumps({"hazard": "fire", "people_count": 2})
    llm = FakeLLM([facts, "சரி.", facts, "சரி."])
    await sms_intake("fire in the next house, smoke everywhere", None, llm, Store(tmp_path / "a.db"), load_gazetteer(), load_guidance())
    assert "GEN-01" not in llm.calls[1][0]["content"]
    await sms_intake("fire in the next house, smoke everywhere", (12.98, 80.22), llm, Store(tmp_path / "b.db"), load_gazetteer(),
                     load_guidance())
    assert "GEN-01" in llm.calls[3][0]["content"]


async def test_same_sms_twice_is_one_incident_and_no_new_tokens(tmp_path):
    # SMS gateways retry and people resend: with no GPS nothing else would merge the two pins
    store = Store(tmp_path / "p.db")
    llm = FakeLLM([json.dumps({"locality": "Velachery", "people_count": 4, "hazard": "flood"}), "சரி, உதவி ஏற்பாடு."])
    a, r1 = await sms_intake(SMS, None, llm, store, load_gazetteer(), load_guidance())
    b, r2 = await sms_intake("  " + SMS.replace(" ", "  ") + " ", None, llm, store, load_gazetteer(), load_guidance())
    assert b.id == a.id and len(store.list_incidents()) == 1 and r2 == r1 and len(llm.calls) == 2
    store.resolve(a.id)  # after the incident is closed, the same words are a new emergency
    llm.replies = [json.dumps({"locality": "Velachery", "hazard": "flood"}), "சரி."]
    c, _ = await sms_intake(SMS, None, llm, store, load_gazetteer(), load_guidance())
    assert c.id != a.id


async def test_romanised_sms_is_answered_in_the_language_the_llm_heard(tmp_path):
    store = Store(tmp_path / "p.db")
    llm = FakeLLM([json.dumps({"hazard": "flood", "locality": "Saidapet", "caller_language": "hi-IN"}), "Ghabraiye mat."])
    inc, _ = await sms_intake("Saidapet mein paani ghar ke andar aa gaya, 3 log hain", None, llm, store,
                              load_gazetteer(), load_guidance())
    assert store.call_lang(inc.call_ids[0]) == "hi-IN" and "Reply in Hindi" in llm.calls[1][0]["content"]
