"""Pukaar domain: facts, explainable severity, location matching, dedup and slot order (design §7)."""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher

from pydantic import BaseModel, model_validator

from .data import Place

HAZARDS = {"flood", "cyclone", "landslide", "fire", "building_collapse", "medical", "other"}
WATER_LEVELS = {"none", "ankle", "knee", "waist", "chest", "neck"}
VULNERABLE = {"infant", "child", "elderly", "pregnant", "disabled", "sick"}
INJURIES = {"bleeding", "fracture", "unconscious", "burn", "other"}
MEDICAL = {"oxygen", "labour", "dialysis", "insulin", "medication"}
NEEDS = {"boat", "ambulance", "food", "water", "medicine", "evacuation"}
_ENUMS = {"hazard": HAZARDS, "water_level": WATER_LEVELS}
_SETS = {"vulnerable": VULNERABLE, "injuries": INJURIES, "medical_needs": MEDICAL, "needs": NEEDS}

KEYTERMS = [
    "flood", "water", "roof", "boat", "rescue", "ambulance", "current", "landslide", "cyclone", "trapped",
    "oxygen", "insulin", "pregnant", "baby", "elderly", "bleeding", "unconscious", "NDRF", "terrace",
    "bus depot", "lake", "வெள்ளம்", "बाढ़", "Velachery", "Tambaram", "Mudichur", "Pallikaranai", "Adyar",
    "Saidapet", "Varadharajapuram", "Madipakkam", "Semmencherry", "Perungudi", "Kotturpuram",
]


class Facts(BaseModel):
    locality: str | None = None
    landmark: str | None = None
    lat: float | None = None
    lon: float | None = None
    hazard: str | None = None
    people_count: int | None = None
    trapped: bool | None = None
    on_roof: bool | None = None
    water_level: str | None = None
    vulnerable: list[str] = []
    injuries: list[str] = []
    medical_needs: list[str] = []
    needs: list[str] = []
    caller_language: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _drop_invalid(cls, d):
        """Unknown enum values become None / are removed from lists, so LLM output never raises."""
        if not isinstance(d, dict):
            return d
        d = {k: v for k, v in d.items() if v is not None}
        for k, allowed in _ENUMS.items():
            if k in d and d[k] not in allowed:
                d.pop(k)
        for k, allowed in _SETS.items():
            if k in d:
                v = d[k] if isinstance(d[k], list) else [d[k]]
                d[k] = list(dict.fromkeys(x for x in v if x in allowed))
        if "people_count" in d:
            try:
                d["people_count"] = int(d["people_count"])
            except (TypeError, ValueError):
                d.pop("people_count")
        return d


def merge_facts(old: Facts, new: Facts) -> Facts:
    m = old.model_dump()
    for k, v in new.model_dump().items():
        if isinstance(v, list):
            m[k] = list(dict.fromkeys(m[k] + v))
        elif k == "people_count" and v is not None:
            m[k] = max(v, m[k] or 0)
        elif v is not None:
            m[k] = v
    return Facts(**m)


class Severity(BaseModel):
    score: int
    level: str
    drivers: list[dict]


_HAZARD_PTS = {"flood": 20, "cyclone": 20, "landslide": 35, "fire": 35, "building_collapse": 40, "medical": 25, "other": 10}
_WATER_PTS = {"ankle": 2, "knee": 8, "waist": 18, "chest": 30, "neck": 35}
_VULN_PTS = {"infant": 12, "pregnant": 12, "elderly": 8, "disabled": 8, "sick": 8, "child": 6}
_MED_PTS = {"oxygen": 20, "labour": 20, "dialysis": 12, "insulin": 10, "medication": 5}
_INJ_PTS = {"unconscious": 25, "bleeding": 20, "fracture": 12, "burn": 12, "other": 8}


def score(f: Facts) -> Severity:
    d: list[tuple[str, int]] = []
    if f.hazard:
        d.append((f"Hazard: {f.hazard}", _HAZARD_PTS[f.hazard]))
    if f.water_level in _WATER_PTS:
        d.append((f"Water: {f.water_level}", _WATER_PTS[f.water_level]))
    if f.trapped:
        d.append(("Trapped", 15))
    if f.on_roof:
        d.append(("On roof", 10))
    if f.vulnerable:
        d.append((f"Vulnerable: {', '.join(f.vulnerable)}", min(25, sum(_VULN_PTS[v] for v in f.vulnerable))))
    if f.medical_needs:
        d.append((f"Medical: {', '.join(f.medical_needs)}", min(25, sum(_MED_PTS[m] for m in f.medical_needs))))
    if f.injuries:
        worst = max(f.injuries, key=_INJ_PTS.__getitem__)
        d.append((f"Injury: {worst}", _INJ_PTS[worst]))
    if f.people_count:
        d.append((f"People: {f.people_count}", int(min(10, 1.5 * f.people_count) + 0.5)))
    total = min(100, sum(p for _, p in d))
    level = "critical" if total >= 70 else "high" if total >= 45 else "medium" if total >= 25 else "low"
    return Severity(score=total, level=level, drivers=[{"label": k, "contribution": v} for k, v in d if v])


def _tokens(s: str) -> list[str]:
    # split on spaces only: Tamil vowel signs are not \w, so \W-splitting would break words
    return re.sub(r"[.,!?;:()\"'\-]", " ", s.casefold()).split()


def _match(text: str, places: list[Place]) -> tuple[Place, float] | None:
    toks = _tokens(text)
    flat = " ".join(toks)
    best: tuple[Place, float] | None = None
    for p in places:
        for name in [p.name, *p.aliases]:
            nt = _tokens(name)
            n = " ".join(nt)
            if len(n) >= 5 and n in flat:
                r = 1.0
            else:
                r = max((SequenceMatcher(None, n, " ".join(toks[i:i + len(nt)])).ratio()
                         for i in range(len(toks) - len(nt) + 1)), default=0.0)
            if r >= (0.9 if len(n) < 6 else 0.75) and (best is None or r > best[1]):  # short names: one typo is a lot
                best = (p, r)
    return best


def locate(f: Facts, places: list[Place], gps: tuple[float, float] | None) -> tuple[float, float, str, float] | None:
    """Returns (lat, lon, source "gps"|"landmark"|"both", confidence) or None. GPS wins for coordinates."""
    hit = next((m for t in (f.locality, f.landmark) if t and (m := _match(t, places))), None)
    if gps and hit:
        return gps[0], gps[1], "both", 0.9
    if gps:
        return gps[0], gps[1], "gps", 0.7
    if hit:
        return hit[0].lat, hit[0].lon, "landmark", round(hit[1] * 0.8, 2)
    return None


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


class Incident(BaseModel):
    id: str
    call_ids: list[str]
    facts: Facts
    lat: float | None = None
    lon: float | None = None
    loc_source: str = ""
    loc_confidence: float = 0.0
    severity: Severity
    status: str = "new"  # new | dispatched | resolved
    dispatch: dict | None = None  # {team, note, eta}
    guidance_given: list[str] = []
    created_at: float
    updated_at: float


MERGE_WINDOW_S = 3 * 3600


def should_merge(a: Incident, b_facts: Facts, b_latlon: tuple[float, float] | None, now: float) -> bool:
    if a.status == "resolved" or now - a.updated_at > MERGE_WINDOW_S:
        return False
    if a.facts.hazard and b_facts.hazard and a.facts.hazard != b_facts.hazard:
        return False
    if b_latlon and a.lat is not None and haversine_m((a.lat, a.lon), b_latlon) < 300:
        return True
    fa, fb = a.facts, b_facts
    return bool(fa.locality and fb.locality and fa.landmark and fb.landmark
                and fa.locality.casefold() == fb.locality.casefold()
                and SequenceMatcher(None, fa.landmark.casefold(), fb.landmark.casefold()).ratio() >= 0.7)


def next_slot(f: Facts, asked: set[str] | frozenset[str] = frozenset()) -> str | None:
    """The first missing fact to ask about; `asked` skips slots the caller already answered with nothing."""
    missing = {
        "location": not (f.locality or f.landmark),
        "people": f.people_count is None,
        "injuries": not (f.injuries or f.medical_needs),
        "water_level": f.water_level is None,
        "vulnerable": not f.vulnerable,
    }
    return next((s for s, m in missing.items() if m and s not in asked), None)
