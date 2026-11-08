import re

from pukaar.data import load_gazetteer, load_guidance


def test_gazetteer_covers_chennai():
    places = load_gazetteer()
    assert len(places) >= 35
    for p in places:
        assert 12.75 <= p.lat <= 13.35 and 79.95 <= p.lon <= 80.35, p.name
    velachery = next(p for p in places if p.name == "Velachery")
    assert "வேளச்சேரி" in velachery.aliases


def test_guidance_kb():
    kb = load_guidance()
    ids = [g.id for g in kb]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[A-Z]{3}-\d{2}", i) for i in ids)
    assert sum("flood" in g.hazards for g in kb) >= 3
