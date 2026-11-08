import json
import random

from voice_core.testing import FakeLLM

from pukaar.data import load_gazetteer
from pukaar.domain import haversine_m
from pukaar.sim import make_case, run_surge
from pukaar.store import Store


def test_make_case_is_plausible_and_seeded():
    places = load_gazetteer()
    c = make_case(random.Random(3), places)
    assert c.truth.locality in {p.name for p in places} and c.lang in {"ta-IN", "hi-IN", "en-IN", "te-IN"}
    assert c.truth.hazard and c.truth.people_count and c.truth.water_level
    p = next(p for p in places if p.name == c.truth.locality)
    assert haversine_m((p.lat, p.lon), c.gps) < 200
    assert make_case(random.Random(3), places) == c


def test_duplicate_case_reuses_location():
    places = load_gazetteer()
    first = make_case(random.Random(1), places)
    dup = make_case(random.Random(2), places, near=first)
    assert haversine_m(first.gps, dup.gps) < 150 and dup.truth.hazard == first.truth.hazard


async def test_run_surge_creates_and_merges_incidents(tmp_path):
    store = Store(tmp_path / "s.db")
    facts = json.dumps({"hazard": "flood", "locality": "Velachery", "people_count": 3})
    llm = FakeLLM(["Help, water inside!", facts] * 3)
    events = []

    async def emit(m):
        events.append(m)

    out = await run_surge(3, llm, store, load_gazetteer(), emit, random.Random(0), delay=0, dup_rate=1.0)
    assert out == {"calls": 3, "incidents": 1}
    assert sum(e["type"] == "incident" for e in events) == 3 and store.kpis()["calls"] == 3
    assert len(store.list_incidents()[0].call_ids) == 3


async def test_surge_records_then_replays_without_llm(tmp_path):
    from pukaar.sim import replay_surge
    rec = tmp_path / "rec.json"
    facts = json.dumps({"hazard": "flood", "locality": "Vayasar Padi", "people_count": 2})
    llm = FakeLLM(["Thanni varudhu!", facts] * 2)

    async def emit(m):
        pass

    await run_surge(2, llm, Store(tmp_path / "a.db"), load_gazetteer(), emit, random.Random(5), delay=0, record=rec)
    rows = json.loads(rec.read_text())
    assert len(rows) == 2 and rows[0]["text"] == "Thanni varudhu!" and rows[0]["facts"]["people_count"] == 2
    store = Store(tmp_path / "b.db")
    out = await replay_surge(rows, store, load_gazetteer(), emit, delay=0)
    assert out["calls"] == 2 and store.list_incidents()[0].channel == "text"


async def test_surge_skips_caller_when_extraction_stays_empty(tmp_path):
    async def emit(m):
        pass
    llm = FakeLLM(["Help!", "not json", "still not json"])
    out = await run_surge(1, llm, Store(tmp_path / "c.db"), load_gazetteer(), emit, random.Random(0), delay=0, retry_wait=0)
    assert out["calls"] == 0
