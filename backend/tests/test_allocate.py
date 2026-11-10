import pytest
from fastapi.testclient import TestClient
from voice_core.config import Settings
from voice_core.testing import FakeLLM

from pukaar.allocate import MOBILISE_MIN, ROUTE_FACTOR, Team, eta_minutes, live_status, load_teams, needs, plan, recommend
from pukaar.app import create_app
from pukaar.data import load_gazetteer
from pukaar.domain import Facts, Incident, haversine_m, score

VELACHERY = (12.97726, 80.22092)


def team(id_, type_, lat=VELACHERY[0], lon=VELACHERY[1], capacity=8, speed=12.0, status="available"):
    return Team(id=id_, name=f"Team {id_}", type=type_, base="Velachery", lat=lat, lon=lon, capacity=capacity,
                speed_kmh=speed, status=status)


def incident(id_="i1", lat=VELACHERY[0], lon=VELACHERY[1], status="new", created=0.0, dispatch=None, **facts):
    f = Facts(**facts)
    return Incident(id=id_, call_ids=[f"c{id_}"], facts=f, severity=score(f), lat=lat, lon=lon, status=status,
                    dispatch=dispatch, created_at=created, updated_at=created)


def test_roster_is_valid_and_based_on_the_gazetteer():
    places = {p.name: p for p in load_gazetteer()}
    teams = load_teams()
    assert len(teams) >= 8 and len({t.id for t in teams}) == len(teams)
    assert {t.type for t in teams} == {"boat", "fire", "ambulance", "medical"}
    for t in teams:
        assert (t.lat, t.lon) == (places[t.base].lat, places[t.base].lon)
        assert t.capacity > 0 and t.speed_kmh > 0 and t.status in {"available", "busy"}


@pytest.mark.parametrize("facts, primary", [
    ({"hazard": "flood", "water_level": "chest"}, ["boat"]),
    ({"hazard": "flood", "water_level": "knee", "on_roof": True}, ["boat"]),
    ({"hazard": "flood", "water_level": "none", "trapped": True}, []),  # dry but stuck: a crew, not a boat
    ({"hazard": "fire"}, ["fire"]),
    ({"hazard": "building_collapse"}, ["fire"]),
    ({"hazard": "flood", "water_level": "ankle", "injuries": ["bleeding"]}, ["ambulance", "medical"]),
    ({"hazard": "medical"}, ["ambulance", "medical"]),
])
def test_needs_match_the_facts(facts, primary):
    assert needs(incident(**facts))["primary"] == primary


def test_deep_water_picks_a_boat_and_never_an_ambulance():
    inc = incident(hazard="flood", water_level="chest", people_count=4, medical_needs=["insulin"])
    recs = recommend(inc, [team("amb", "ambulance"), team("boat", "boat"), team("fire", "fire")])
    assert recs[0]["type"] == "boat"
    assert "ambulance" not in {r["type"] for r in recs}  # cannot drive through chest-deep water
    assert "water chest-high" in recs[0]["summary"] and "fits 4 people" in recs[0]["summary"]


def test_medical_need_in_shallow_water_picks_an_ambulance():
    inc = incident(hazard="flood", water_level="ankle", people_count=1, injuries=["unconscious"])
    recs = recommend(inc, [team("boat", "boat"), team("amb", "ambulance", capacity=2, speed=30)])
    assert [r["type"] for r in recs] == ["ambulance"]  # a boat is the wrong kind of team here


def test_fire_picks_fire_and_rescue():
    recs = recommend(incident(hazard="fire", people_count=3), [team("boat", "boat"), team("fire", "fire", speed=30)])
    assert recs[0]["type"] == "fire" and recs[0]["fit"] == "matches"


def test_capacity_prefers_the_team_that_fits_everyone():
    inc = incident(hazard="flood", water_level="waist", people_count=6)
    small, big = team("small", "boat", capacity=4), team("big", "boat", capacity=8)
    recs = recommend(inc, [small, big])
    assert recs[0]["team_id"] == "big"
    assert "carries 4 of 6, more trips needed" in recs[1]["reasons"]


def test_eta_math_and_nearer_team_first():
    assert eta_minutes(0, 12) == MOBILISE_MIN
    assert eta_minutes(10, 30) == round(MOBILISE_MIN + 10 * ROUTE_FACTOR / 30 * 60) == 31
    far = (13.0827, 80.2707)  # central Chennai, ~13 km away
    inc = incident(hazard="flood", water_level="chest")
    recs = recommend(inc, [team("far", "boat", *far), team("near", "boat")])
    assert [r["team_id"] for r in recs] == ["near", "far"]
    km = haversine_m(VELACHERY, far) / 1000
    assert recs[1]["distance_km"] == round(km, 1) and recs[1]["eta_min"] == eta_minutes(km, 12)
    assert recs[0]["eta"] == f"~{MOBILISE_MIN} min"


def test_busy_teams_are_never_recommended_and_dispatch_makes_a_team_busy():
    boat = team("b1", "boat")
    assert recommend(incident(hazard="flood", water_level="chest"), [team("b0", "boat", status="busy")]) == []
    on_job = incident("x", hazard="flood", status="dispatched", dispatch={"team": boat.name, "note": "", "eta": None})
    assert live_status([boat], [on_job])[0].status == "busy"
    done = on_job.model_copy(update={"status": "resolved"})
    assert live_status([boat], [done])[0].status == "available"  # free again once the incident is resolved


def test_no_clear_need_gets_only_a_general_rescue_crew():
    inc = incident(hazard="flood", water_level="none", on_roof=True)  # dry roof: no boat, nothing medical
    recs = recommend(inc, [team("b", "boat"), team("m", "medical"), team("f", "fire")])
    assert [(r["type"], r["fit"]) for r in recs] == [("fire", "general rescue crew")]
    assert recommend(incident(lat=13.0, lon=80.2), [team("m", "medical")]) == []  # missed call, no facts yet


def test_unlocated_incident_still_ranked_but_without_eta():
    recs = recommend(incident(lat=None, lon=None, hazard="fire"), [team("f", "fire")])
    assert recs[0]["eta_min"] is None and "location unknown, no ETA" in recs[0]["reasons"]


def test_empty_roster():
    inc = incident(hazard="flood", water_level="chest")
    assert recommend(inc, []) == []
    p = plan([inc], [])
    assert p["assignments"] == [] and p["unassigned"][0]["reason"] == "every team is busy"


def test_plan_orders_by_severity_then_age_and_never_double_books():
    worst = incident("worst", hazard="flood", water_level="neck", trapped=True, people_count=5, created=50)
    old = incident("old", hazard="flood", water_level="chest", people_count=2, created=10)
    young = incident("young", hazard="flood", water_level="chest", people_count=2, created=20)
    gone = incident("gone", hazard="flood", water_level="chest", status="dispatched")
    nowhere = incident("nowhere", lat=None, lon=None, hazard="flood", water_level="chest")
    p = plan([young, nowhere, old, worst, gone], [team("b1", "boat"), team("b2", "boat")])
    assert [a["incident_id"] for a in p["assignments"]] == ["worst", "old"]
    assert len({a["team_id"] for a in p["assignments"]}) == 2
    left = {u["incident_id"]: u["reason"] for u in p["unassigned"]}
    assert left["young"] == "every team is busy" and left["nowhere"].startswith("location unknown")
    assert "gone" not in left and p["teams_free"] == []


def test_plan_reports_no_suitable_team():
    p = plan([incident(hazard="fire")], [team("b", "boat")])
    assert p["unassigned"][0]["reason"] == "no suitable team free" and p["teams_free"] == ["Team b"]


def test_api_recommend_plan_and_teams(tmp_path):
    settings = Settings(sample_rate=8000, cache_dir=tmp_path / "cache")
    roster = [team("b1", "boat"), team("a1", "ambulance", capacity=2, speed=30)]
    with TestClient(create_app(settings, session_factory=lambda *a, **k: None, intel_llm=FakeLLM([]),
                               teams=roster)) as c:
        store = c.app.state.store
        cid = store.create_call("ta-IN")
        inc = store.upsert_incident(cid, Facts(hazard="flood", water_level="chest", people_count=4),
                                    (*VELACHERY, "gps", 0.7))
        assert c.get("/api/incidents/nope/recommend").status_code == 404
        r = c.get(f"/api/incidents/{inc.id}/recommend").json()
        assert r["teams_free"] == 2 and [x["team_id"] for x in r["recommendations"]] == ["b1"]
        assert c.get("/api/plan").json()["assignments"][0]["team"] == "Team b1"
        # a human confirms through the existing dispatch endpoint; the team then shows busy everywhere
        c.post(f"/api/incidents/{inc.id}/dispatch", json={"team": "Team b1", "eta": r["recommendations"][0]["eta"]})
        assert {t["id"]: t["status"] for t in c.get("/api/teams").json()} == {"b1": "busy", "a1": "available"}
        assert c.get("/api/plan").json() == {"assignments": [], "unassigned": [], "teams_free": ["Team a1"]}
