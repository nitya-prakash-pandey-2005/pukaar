"""Hotspots: open incidents that sit close together, so one boat run or one relief camp can serve them all.

Single-linkage clustering: two located, unresolved incidents within `radius_m` of each other join the same cluster
(chains too: A-B 400 m and B-C 400 m make one cluster even if A-C is 800 m). Pure function, no map library.
"""

from __future__ import annotations

from .domain import Incident, haversine_m

RANK = {"critical": 3, "high": 2, "medium": 1, "low": 0}


def clusters(incidents: list[Incident], radius_m: float = 500) -> list[dict]:
    """Every cluster (singletons included), most urgent first: highest severity, then most people."""
    pts = [i for i in incidents if i.lat is not None and i.lon is not None and i.status != "resolved"]
    parent = list(range(len(pts)))

    def root(k: int) -> int:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            if haversine_m((pts[a].lat, pts[a].lon), (pts[b].lat, pts[b].lon)) <= radius_m:
                parent[root(a)] = root(b)
    groups: dict[int, list[Incident]] = {}
    for k, inc in enumerate(pts):
        groups.setdefault(root(k), []).append(inc)

    out = []
    for members in groups.values():
        lat = sum(i.lat for i in members) / len(members)
        lon = sum(i.lon for i in members) / len(members)
        worst = max(members, key=lambda i: (RANK[i.severity.level], i.severity.score))
        places = list(dict.fromkeys(i.facts.locality or i.facts.landmark for i in members
                                    if i.facts.locality or i.facts.landmark))
        out.append({
            "lat": round(lat, 6), "lon": round(lon, 6),
            "count": len(members),
            "people": sum(i.facts.people_count or 1 for i in members),
            "max_level": worst.severity.level, "max_score": worst.severity.score,
            "spread_m": round(max(haversine_m((lat, lon), (i.lat, i.lon)) for i in members)),
            "places": places,
            "waiting": sum(i.status == "new" for i in members),
            "incident_ids": [i.id for i in members],
        })
    out.sort(key=lambda c: (-RANK[c["max_level"]], -c["max_score"], -c["people"], -c["count"]))
    return out


def hotspots(incidents: list[Incident], radius_m: float = 500) -> dict:
    """Map layer and list: every cluster, and how many are real hotspots (two or more incidents)."""
    cs = clusters(incidents, radius_m)
    return {"radius_m": radius_m, "clusters": cs, "hotspots": sum(c["count"] >= 2 for c in cs)}
