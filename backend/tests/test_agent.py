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
    assert "people" in a.asked


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
