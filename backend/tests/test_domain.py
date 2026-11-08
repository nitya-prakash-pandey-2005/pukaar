import pytest

from pukaar.data import load_gazetteer
from pukaar.domain import (
    KEYTERMS, Facts, Incident, haversine_m, locate, merge_facts, next_slot, score, should_merge,
)


@pytest.fixture
def places():
    return load_gazetteer()


def test_score_critical_example():
    f = Facts(hazard="flood", water_level="chest", on_roof=True, vulnerable=["elderly", "infant"],
              medical_needs=["insulin"], people_count=4)
    s = score(f)
    assert s.score == 20 + 30 + 10 + 20 + 10 + 6 and s.level == "critical"  # 96
    assert {"label": "Water: chest", "contribution": 30} in s.drivers


def test_score_caps_and_low():
    assert score(Facts(hazard="other")).level == "low"
    assert score(Facts(hazard="building_collapse", water_level="neck", trapped=True, on_roof=True,
                       vulnerable=["infant", "pregnant", "elderly"], medical_needs=["oxygen", "labour"],
                       injuries=["unconscious"], people_count=20)).score == 100


def test_injuries_take_max_not_sum():
    assert score(Facts(injuries=["bleeding", "fracture"])).score == 20


def test_invalid_enum_values_are_dropped():
    f = Facts.model_validate({"hazard": "tsunami", "water_level": "knee", "vulnerable": ["infant", "alien"]})
    assert f.hazard is None and f.water_level == "knee" and f.vulnerable == ["infant"]


def test_merge_facts():
    old = Facts(locality="Velachery", people_count=4, vulnerable=["elderly"])
    new = Facts(water_level="waist", people_count=3, vulnerable=["infant"])
    m = merge_facts(old, new)
    assert m.locality == "Velachery" and m.water_level == "waist" and m.people_count == 4
    assert m.vulnerable == ["elderly", "infant"]


def test_locate_by_landmark_alias(places):
    lat, lon, src, conf = locate(Facts(landmark="near வேளச்சேரி bus depot"), places, None)
    assert src == "landmark" and abs(lat - 12.98) < 0.05


def test_locate_misspelt_locality_and_gps(places):
    lat, lon, src, _ = locate(Facts(locality="Velacheri"), places, None)
    assert src == "landmark" and abs(lon - 80.22) < 0.05
    lat, lon, src, _ = locate(Facts(locality="Tambaram"), places, (12.9, 80.1))
    assert (lat, lon, src) == (12.9, 80.1, "both")
    assert locate(Facts(), places, (12.9, 80.1))[2] == "gps"
    assert locate(Facts(landmark="the big temple"), places, None) is None
    assert locate(Facts(landmark="aadi masam"), places, None) is None  # not Avadi


def _incident(**kw):
    base = dict(id="i1", call_ids=["c1"], facts=Facts(hazard="flood", locality="Velachery", landmark="bus depot"),
                lat=12.9800, lon=80.2200, severity=score(Facts()), created_at=0.0, updated_at=0.0)
    return Incident(**(base | kw))


def test_dedup_merges_same_roof():
    a = _incident()
    near = (12.9800 + 120 / 111_000, 80.2200)  # ~120 m north
    far = (12.9800 + 900 / 111_000, 80.2200)
    f = Facts(hazard="flood")
    assert 100 < haversine_m((a.lat, a.lon), near) < 140
    assert should_merge(a, f, near, now=40 * 60)
    assert not should_merge(a, f, far, now=40 * 60)
    assert not should_merge(a, f, near, now=4 * 3600)               # too old
    assert not should_merge(a, Facts(hazard="fire"), near, now=60)  # other hazard


def test_dedup_same_locality_similar_landmark_far_gps():
    a = _incident()
    f = Facts(hazard="flood", locality="velachery", landmark="Bus Depot")
    assert should_merge(a, f, (13.05, 80.25), now=60)


def test_next_slot_order():
    assert next_slot(Facts()) == "location"
    assert next_slot(Facts(locality="Velachery")) == "people"
    assert next_slot(Facts(landmark="temple", people_count=3)) == "injuries"
    assert next_slot(Facts(landmark="temple", people_count=3), asked={"injuries"}) == "water_level"
    full = Facts(landmark="t", people_count=1, injuries=["burn"], water_level="knee", vulnerable=["child"])
    assert next_slot(full) is None


def test_keyterms():
    assert 10 <= len(KEYTERMS) <= 40 and "flood" in KEYTERMS
