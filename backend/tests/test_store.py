"""Store: dedup edge cases, queue order, callbacks and KPIs (SQLite in a temp folder)."""

import pytest
from voice_core.types import Turn

from pukaar.domain import Facts
from pukaar.store import Store

ROOF = {"hazard": "flood", "locality": "Velachery", "landmark": "bus depot", "water_level": "waist", "people_count": 3}


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "p.db")


def test_merged_incident_without_a_position_adopts_the_next_callers_gps(store):
    a, b = store.create_call("ta-IN"), store.create_call("hi-IN")
    first = store.upsert_incident(a, Facts(**ROOF), None)  # caller named the place but has no GPS
    assert first.lat is None
    second = store.upsert_incident(b, Facts(**{**ROOF, "landmark": "bus depo"}), (12.98, 80.22, "gps", 0.7))
    assert second.id == first.id and second.call_ids == [a, b]
    assert (second.lat, second.lon, second.loc_source) == (12.98, 80.22, "gps")


def test_a_resolved_incident_never_absorbs_new_reports(store):
    a, b = store.create_call("ta-IN"), store.create_call("ta-IN")
    first = store.upsert_incident(a, Facts(**ROOF), (12.98, 80.22, "gps", 0.7))
    store.resolve(first.id)
    second = store.upsert_incident(b, Facts(**ROOF), (12.98, 80.22, "gps", 0.7))
    assert second.id != first.id and second.status == "new"


def test_queue_is_most_severe_first_and_status_filter_works(store):
    low = store.upsert_incident(store.create_call("en-IN"), Facts(hazard="flood", water_level="ankle"), None)
    high = store.upsert_incident(store.create_call("en-IN"),
                                 Facts(hazard="building_collapse", trapped=True, injuries=["unconscious"]), None)
    assert [i.id for i in store.list_incidents()] == [high.id, low.id]
    store.dispatch(high.id, "NDRF 1", "", None)
    assert [i.id for i in store.list_incidents("new")] == [low.id]
    assert [i.id for i in store.list_incidents("dispatched")] == [high.id]


def test_unknown_ids_return_none_not_errors(store):
    assert store.get_incident("missing") is None and store.get_call("missing") is None
    assert store.dispatch("missing", "team", "", None) is None and store.resolve("missing") is None
    assert store.call_lang("missing") == "en-IN"  # replies to an unknown call default to English
    store.add_guidance("missing", ["FLD-01"])  # no incident linked: a no-op


def test_guidance_history_is_deduplicated(store):
    cid = store.create_call("ta-IN")
    inc = store.upsert_incident(cid, Facts(**ROOF), None)
    store.add_guidance(cid, ["FLD-01", "FLD-03"])
    store.add_guidance(cid, ["FLD-03", "MED-02"])
    store.add_guidance(cid, [])
    assert store.get_incident(inc.id).guidance_given == ["FLD-01", "FLD-03", "MED-02"]


def test_callbacks_are_per_call_and_in_order(store):
    a, b = store.create_call("ta-IN"), store.create_call("hi-IN")
    first = store.queue_callback(a, "one", "ta-IN")
    second = store.queue_callback(a, "two", "ta-IN")
    store.queue_callback(b, "other", "hi-IN")
    assert [c["id"] for c in store.pending_callbacks(a)] == [first, second]
    assert [c["text"] for c in store.pending_callbacks(b)] == ["other"]


def test_kpis_count_open_incidents_only_and_average_answer_time(store):
    assert store.kpis() == {"calls": 0, "avg_answer_s": None, "critical_open": 0, "people_affected": 0}
    a, b = store.create_call("ta-IN"), store.create_call("ta-IN")
    store.add_reply_latency(a, 1.0)
    store.add_reply_latency(a, 2.0)
    crit = store.upsert_incident(a, Facts(hazard="building_collapse", water_level="chest", people_count=5), None)
    store.upsert_incident(b, Facts(hazard="fire"), None)  # no head count: counts as 1 person
    assert store.kpis() == {"calls": 2, "avg_answer_s": 1.5, "critical_open": 1, "people_affected": 6}
    store.resolve(crit.id)
    assert store.kpis()["critical_open"] == 0 and store.kpis()["people_affected"] == 1


def test_recent_caller_call_ignores_case_spacing_and_agent_lines(store):
    cid = store.create_call("en-IN")
    store.add_turn(cid, Turn("caller", "Water  is in the HOUSE", 0.0))
    store.add_turn(cid, Turn("pukaar", "where are you", 0.0))
    assert store.recent_caller_call("water is in the house", 0.0) == cid
    assert store.recent_caller_call("where are you", 0.0) is None  # only the caller's own words count
    assert store.recent_caller_call("water is in the house", 9e12) is None  # outside the window
