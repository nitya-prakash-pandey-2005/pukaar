from fastapi.testclient import TestClient
from voice_core.config import Settings
from voice_core.testing import FakeLLM

from pukaar.app import create_app
from pukaar.domain import Facts, Incident, score
from pukaar.hotspots import clusters, hotspots
from pukaar.sitrep import sitrep

NOW = 10_000.0


def incident(id_, lat=12.97726, lon=80.22092, status="new", created=NOW - 600, dispatch=None, **facts):
    f = Facts(**facts)
    return Incident(id=id_, call_ids=[f"c{id_}"], facts=f, severity=score(f), lat=lat, lon=lon, status=status,
                    dispatch=dispatch, created_at=created, updated_at=created)


# ------------------------------------------------------------------ SitRep
def test_sitrep_with_no_incidents():
    r = sitrep([], calls=0, now=NOW)
    assert r["incidents"] == 0 and r["people_affected"] == 0 and r["hotspots"] == [] and r["timeline"] == []
    assert r["critical_waiting"] == {"count": 0, "avg_min": None, "oldest_min": None}
    assert "Critical incidents waiting: none" in r["markdown"] and "- nothing yet" in r["markdown"]


def test_sitrep_totals_waits_hotspots_and_markdown():
    crit = dict(hazard="flood", water_level="chest", trapped=True, on_roof=True, vulnerable=["elderly", "infant"])
    incs = [
        incident("a", locality="Velachery", people_count=4, created=NOW - 1200, **crit),  # critical, 20 min
        incident("b", locality="Velachery", people_count=2, created=NOW - 600, medical_needs=["oxygen"], **crit),
        incident("c", locality="Adyar", people_count=3, hazard="flood", water_level="knee", vulnerable=["disabled"],
                 status="dispatched", dispatch={"team": "NDRF Boat 1", "note": "", "eta": "~9 min"}),
        incident("d", locality="Saidapet", people_count=9, hazard="flood", status="resolved"),
        incident("e", lat=None, lon=None, people_count=None),  # missed call: no facts yet
    ]
    assert [i.severity.level for i in incs[:2]] == ["critical", "critical"]
    r = sitrep(incs, calls=7, now=NOW)
    assert r["calls"] == 7 and r["incidents"] == 5 and r["by_level"]["critical"] == 2
    assert r["status"] == {"waiting": 3, "dispatched": 1, "resolved": 1}
    assert r["people_affected"] == 4 + 2 + 3 + 1  # open incidents only; unknown counts as one person
    assert r["vulnerable"] == {"elderly": 2, "children": 2, "medical": 1, "disabled": 1}
    assert r["trapped"] == 2 and r["on_roof"] == 2
    assert r["critical_waiting"] == {"count": 2, "avg_min": 15, "oldest_min": 20}
    assert r["hotspots"][0] == {"place": "Velachery", "incidents": 2, "people": 6, "max_level": "critical"}
    assert any("NDRF Boat 1 dispatched to Adyar, ETA ~9 min" == e["text"] for e in r["timeline"])
    assert any(e["text"] == "Saidapet resolved" for e in r["timeline"])
    md = r["markdown"]
    assert md.startswith("# Situation report: Chennai floods") and "- Velachery: 2 incidents, 6 people, worst critical" in md
    assert "Critical incidents waiting: 2 (average 15 min, oldest 20 min)" in md


# ------------------------------------------------------------------ hotspots
def test_clusters_within_500m_chain_and_skip_resolved_and_unlocated():
    base = (13.0, 80.2)
    deg = 400 / 111_195  # ~400 m of latitude
    incs = [
        incident("a", base[0], base[1], people_count=2, hazard="flood", water_level="knee"),
        incident("b", base[0] + deg, base[1], people_count=3, hazard="flood", water_level="chest", trapped=True,
                 vulnerable=["elderly"]),
        incident("c", base[0] + 2 * deg, base[1], hazard="fire"),  # 800 m from a, 400 m from b: chains in
        incident("far", 13.1, 80.3, people_count=5, hazard="flood"),
        incident("done", base[0], base[1], status="resolved", hazard="flood"),
        incident("nowhere", None, None, hazard="flood"),
    ]
    cs = clusters(incs)
    assert len(cs) == 2
    top = cs[0]
    assert sorted(top["incident_ids"]) == ["a", "b", "c"] and top["count"] == 3 and top["people"] == 6
    assert top["max_level"] == incs[1].severity.level and top["max_score"] == incs[1].severity.score
    assert abs(top["lat"] - (base[0] + deg)) < 1e-6 and 390 <= top["spread_m"] <= 410
    assert cs[1]["incident_ids"] == ["far"]
    assert hotspots(incs)["hotspots"] == 1
    assert len(clusters(incs, radius_m=300)) == 4  # nothing within 300 m: every located incident on its own


def test_clusters_empty():
    assert clusters([]) == [] and hotspots([]) == {"radius_m": 500, "clusters": [], "hotspots": 0}


def test_api_sitrep_and_hotspots(tmp_path):
    settings = Settings(sample_rate=8000, cache_dir=tmp_path / "cache")
    with TestClient(create_app(settings, session_factory=lambda *a, **k: None, intel_llm=FakeLLM([]))) as c:
        assert c.get("/api/sitrep").json()["incidents"] == 0
        store = c.app.state.store
        for _ in range(2):
            cid = store.create_call("ta-IN")
            store.upsert_incident(cid, Facts(hazard="fire", locality="Adyar", people_count=2),
                                  (13.00645, 80.25778, "landmark", 0.8))
        r = c.get("/api/sitrep").json()
        assert r["calls"] == 2 and r["incidents"] == 2 and r["markdown"].startswith("# Situation report")
        h = c.get("/api/hotspots").json()
        assert h["hotspots"] == 1 and h["clusters"][0]["count"] == 2 and h["clusters"][0]["places"] == ["Adyar"]
