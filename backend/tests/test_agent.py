import json

import pytest
from voice_core.testing import FakeLLM
from voice_core.types import Turn

from pukaar.agent import PukaarAgent, deliver_dispatch
from pukaar.data import load_gazetteer, load_guidance
from pukaar.store import Store

FACTS = {"hazard": "flood", "locality": "Velachery", "water_level": "chest", "on_roof": True,
         "vulnerable": ["elderly", "infant"], "medical_needs": ["insulin"], "people_count": 4}
HIST = [Turn("caller", "Velachery, thanni chest varaikkum, naalu peru roof la, paati insulin", 1.0)]


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "p.db")


def make_agent(store, intel_replies, replies=(), gps=None):
    return PukaarAgent(llm=FakeLLM(list(replies)), intel_llm=FakeLLM(intel_replies), store=store,
                       places=load_gazetteer(), kb=load_guidance(), gps=gps)


async def test_turn_produces_incident_and_guarded_reply(store):
    a = make_agent(store, [json.dumps(FACTS)], ["பயப்படாதீங்க. மேல் மாடிக்கு போங்க [[FLD-01]]"])
    evt = await a.on_user_turn(HIST)
    inc = evt["incident"]
    assert evt["type"] == "incident" and inc["severity"]["level"] == "critical"
    assert abs(inc["lat"] - 12.977) < 0.01 and inc["loc_source"] == "landmark"
    said = [s async for s in a.reply_sentences(HIST)]
    assert "[[" not in " ".join(said) and said
    assert len(a.intel_llm.calls) == 1  # reply reused the same extraction
    assert store.get_incident(inc["id"]).guidance_given == ["FLD-01"]


async def test_reply_asks_next_slot_and_falls_back_on_empty_llm(store):
    a = make_agent(store, ['{"locality": "Tambaram"}'], [""])
    said = [s async for s in a.reply_sentences(HIST)]
    assert said and "how many people" in a.llm.calls[0][0]["content"]
    assert "people" not in a.asked  # the fallback line asked nothing, so the question is still due


async def test_question_is_marked_asked_only_once_spoken(store):
    # Groq error (empty), then a guard-blocked reply: the caller heard the safe line twice, never "where are you?"
    a = make_agent(store, ["{}", "{}", "{}"], ["", "The boat reaches you in 10 minutes. Where are you?",
                                               "Stay calm. Which area are you in?"])
    for i in range(3):
        h = HIST + [Turn("caller", f"help {i}", 2.0 + i)]
        said = [s async for s in a.reply_sentences(h)]
        assert said and "where they are" in a.llm.calls[i][0]["content"], f"turn {i} skipped the location question"
    assert a.asked == {"location"}


async def test_unlocated_caller_is_not_told_they_are_on_the_map(store):
    # GEN-01 = "the control room can see you on the map": false with no GPS and no known place
    fire = [Turn("caller", "fire! help!", 1.0)]
    a = make_agent(store, ['{"hazard": "fire"}'], ["ok"])
    [s async for s in a.reply_sentences(fire)]
    assert "FIR-01" in a.llm.calls[0][0]["content"] and "GEN-01" not in a.llm.calls[0][0]["content"]
    b = make_agent(store, ['{"hazard": "fire"}'], ["ok"], gps=(12.98, 80.22))
    [s async for s in b.reply_sentences(fire)]
    assert "GEN-01" in b.llm.calls[0][0]["content"]


async def test_tag_without_words_is_not_logged_as_given(store):
    a = make_agent(store, [json.dumps(FACTS)], ["[[FLD-01]]"])
    inc = (await a.on_user_turn(HIST))["incident"]
    said = [s async for s in a.reply_sentences(HIST)]
    assert said and a.given == set() and store.get_incident(inc["id"]).guidance_given == []


async def test_two_callers_same_roof_merge(store):
    a = make_agent(store, ['{"hazard": "flood", "people_count": 3}'], gps=(12.9800, 80.2200))
    b = make_agent(store, ['{"hazard": "flood", "people_count": 5}'], gps=(12.9805, 80.2203))
    await a.on_user_turn(HIST)
    await b.on_user_turn(HIST)
    incs = store.list_incidents()
    assert len(incs) == 1 and set(incs[0].call_ids) == {a.call_id, b.call_id}
    assert incs[0].facts.people_count == 5


async def test_incident_merges_when_hazard_arrives_later(store):
    a = make_agent(store, ['{"hazard": "flood"}'], gps=(12.9800, 80.2200))
    await a.on_user_turn(HIST)
    b = make_agent(store, ['{"hazard": "fire"}', '{"hazard": "flood"}'], gps=(12.9801, 80.2201))
    await b.on_user_turn(HIST)
    assert len(store.list_incidents()) == 2
    await b.on_user_turn(HIST + [Turn("caller", "sorry, it is flood water", 2.0)])
    assert len(store.list_incidents()) == 1


async def test_no_gps_callers_in_one_locality_stay_separate(store):
    # both are pinned on the Velachery centre; different landmarks = different families (design §7)
    a = make_agent(store, ['{"hazard": "flood", "locality": "Velachery", "landmark": "Vijayanagar bus stand", "people_count": 4}'])
    b = make_agent(store, ['{"hazard": "flood", "locality": "Velachery", "landmark": "Phoenix mall", "people_count": 2}'])
    await a.on_user_turn(HIST)
    await b.on_user_turn(HIST)
    assert len(store.list_incidents()) == 2 and store.kpis()["people_affected"] == 6
    c = make_agent(store, ['{"hazard": "flood", "locality": "Velachery", "landmark": "Phoenix mall", "people_count": 2}'])
    await c.on_user_turn(HIST)  # same landmark: the same family calling again merges
    assert len(store.list_incidents()) == 2


async def test_caller_with_no_hazard_yet_does_not_relabel_a_fire_nearby(store):
    fire = make_agent(store, ['{"hazard": "fire", "people_count": 3}'], gps=(12.9800, 80.2200))
    await fire.on_user_turn(HIST)
    b = make_agent(store, ['{}', '{"hazard": "flood"}'], gps=(12.9809, 80.2200))  # ~100 m away
    await b.on_user_turn(HIST)
    await b.on_user_turn(HIST + [Turn("caller", "water is entering the house", 2.0)])
    fire_inc = store.get_incident(store.get_call(fire.call_id)["incident_id"])
    assert fire_inc.facts.hazard == "fire" and fire_inc.call_ids == [fire.call_id]


async def test_dispatch_after_hangup_queues_callback(store):
    a = make_agent(store, [json.dumps(FACTS)])
    inc = (await a.on_user_turn(HIST))["incident"]
    a.end(30.0)
    inc = store.dispatch(inc["id"], "NDRF Boat 2", "", "20 min")
    await deliver_dispatch(store, inc, FakeLLM(["படகு வருகிறது. 20 நிமிடத்தில் வரும்."]), live={})
    cb = store.pending_callbacks(a.call_id)
    assert len(cb) == 1 and "20" in cb[0]["text"]
    assert store.get_incident(inc.id).status == "dispatched"


async def test_dispatch_live_call_speaks(store):
    a = make_agent(store, [json.dumps(FACTS)])
    inc = (await a.on_user_turn(HIST))["incident"]
    said = []

    async def say(text):
        said.append(text)
    inc = store.dispatch(inc["id"], "Fire & Rescue", "", None)
    await deliver_dispatch(store, inc, FakeLLM(["Team coming in 10 minutes"]), live={a.call_id: say})
    assert len(said) == 1 and "10 minutes" not in said[0]  # no ETA given: time promise blocked
    assert store.pending_callbacks(a.call_id) == []


def test_kpis(store):
    store.create_call("ta-IN")
    k = store.kpis()
    assert k["calls"] == 1 and k["critical_open"] == 0 and k["people_affected"] == 0
