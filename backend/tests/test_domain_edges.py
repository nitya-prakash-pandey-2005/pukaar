"""Edge cases of the explainable severity score, lenient fact parsing and the dedup window."""

import pytest

from pukaar.domain import MERGE_WINDOW_S, Facts, Incident, merge_reports, next_slot, score, should_merge


@pytest.mark.parametrize("facts, points, level", [
    (dict(hazard="building_collapse", water_level="chest"), 70, "critical"),  # 40 + 30: the critical threshold
    (dict(hazard="landslide", on_roof=True), 45, "high"),                      # 35 + 10
    (dict(hazard="flood", water_level="knee", trapped=True), 43, "medium"),    # 20 + 8 + 15
    (dict(hazard="medical"), 25, "medium"),
    (dict(hazard="flood", water_level="ankle"), 22, "low"),
    (dict(), 0, "low"),
])
def test_severity_level_thresholds(facts, points, level):
    s = score(Facts(**facts))
    assert (s.score, s.level) == (points, level)
    assert sum(d["contribution"] for d in s.drivers) == points  # every point is explained by a driver


def test_no_water_and_no_people_add_no_drivers():
    s = score(Facts(hazard="flood", water_level="none", people_count=0))
    assert s.drivers == [{"label": "Hazard: flood", "contribution": 20}]


def test_vulnerable_and_medical_points_are_capped_at_25_each():
    s = score(Facts(vulnerable=["infant", "pregnant", "elderly"], medical_needs=["oxygen", "labour"]))
    assert [d["contribution"] for d in s.drivers] == [25, 25]


def test_people_points_round_and_cap_at_10():
    assert score(Facts(people_count=1)).score == 2   # 1.5 rounds up
    assert score(Facts(people_count=3)).score == 5   # 4.5 rounds up
    assert score(Facts(people_count=50)).score == 10


def test_llm_output_is_coerced_or_dropped_never_raised():
    f = Facts.model_validate({"people_count": "4", "trapped": "yes", "on_roof": "unknown", "vulnerable": "infant",
                              "needs": ["boat", "boat", "helicopter"], "locality": 42, "landmark": None})
    assert f.people_count == 4 and f.trapped is True and f.on_roof is None
    assert f.vulnerable == ["infant"] and f.needs == ["boat"] and f.locality is None
    assert Facts.model_validate({"people_count": -2}).people_count is None
    assert Facts.model_validate({"people_count": "four"}).people_count is None


def test_merge_reports_keeps_the_highest_water_and_any_trapped():
    old = Facts(hazard="flood", water_level="chest", trapped=True, people_count=5)
    new = Facts(hazard="flood", water_level="knee", trapped=False, people_count=2, needs=["boat"])
    m = merge_reports(old, new)
    assert (m.water_level, m.trapped, m.people_count, m.needs) == ("chest", True, 5, ["boat"])


def _incident(**kw):
    base = dict(id="i1", call_ids=["c1"], facts=Facts(hazard="flood", locality="Velachery", landmark="bus depot"),
                lat=12.98, lon=80.22, loc_source="gps", severity=score(Facts()), created_at=0.0, updated_at=0.0)
    return Incident(**(base | kw))


def test_dedup_window_and_status():
    same = Facts(hazard="flood", locality="Velachery", landmark="bus depot")
    assert should_merge(_incident(), same, (12.9801, 80.2201), now=60.0)
    assert not should_merge(_incident(status="resolved"), same, (12.9801, 80.2201), now=60.0)
    assert not should_merge(_incident(), same, (12.9801, 80.2201), now=MERGE_WINDOW_S + 1)  # older than 3 h
    assert not should_merge(_incident(), same.model_copy(update={"hazard": "fire"}), (12.9801, 80.2201), now=60.0)


def test_dedup_by_gps_needs_less_than_300_m():
    other_place = Facts(hazard="flood", locality="Adyar", landmark="school")
    assert should_merge(_incident(), other_place, (12.9820, 80.22), now=1.0)      # about 220 m
    assert not should_merge(_incident(), other_place, (12.9850, 80.22), now=1.0)  # about 560 m


def test_next_slot_returns_none_when_everything_is_known_or_asked():
    full = Facts(locality="Velachery", people_count=2, injuries=["fracture"], water_level="knee", vulnerable=["child"])
    assert next_slot(full) is None
    assert next_slot(Facts(), {"location", "people", "injuries", "water_level", "vulnerable"}) is None
