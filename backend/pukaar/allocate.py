"""Dispatch recommender: which rescue team fits an incident, and a greedy plan for the whole queue.

Pure functions over a synthetic roster (data/teams.json). They only rank and explain; a human dispatcher confirms
every dispatch through POST /api/incidents/{id}/dispatch. Nothing here ever dispatches a team.

Score (0-100), each part explained in plain words:
  need match  50  the team type the facts call for (boat for deep water / trapped / on a roof, ambulance or medical
                  team for injuries and medical needs, fire & rescue for fire, collapse and landslide)
  capacity    15  the team can carry everyone reported (partial credit if not)
  ETA         35  straight line x 1.3 for the road or water route, at the team's speed, plus 5 min to get moving;
                  full marks at 0 min, nothing at 60 min or more
A team that cannot reach the people (an ambulance into waist-deep water) is never recommended.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import cache

from .data import DATA
from .domain import Incident, haversine_m

ROUTE_FACTOR = 1.3  # roads and flooded streets are longer than the straight line
MOBILISE_MIN = 5  # minutes to crew up and leave the base
DEEP = {"waist", "chest", "neck"}  # wheeled vehicles cannot drive through this
TYPE_LABEL = {"boat": "boat", "fire": "fire & rescue", "ambulance": "ambulance", "medical": "medical team"}


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    type: str  # boat | fire | ambulance | medical
    base: str
    lat: float
    lon: float
    capacity: int
    speed_kmh: float
    status: str = "available"  # available | busy


@cache
def load_teams() -> tuple[Team, ...]:
    return tuple(Team(**t) for t in json.loads((DATA / "teams.json").read_text(encoding="utf-8")))


def live_status(teams: tuple[Team, ...] | list[Team], incidents: list[Incident]) -> list[Team]:
    """A team is busy if the roster says so or it is on an open dispatched incident (free again once resolved)."""
    on_job = {(i.dispatch or {}).get("team") for i in incidents if i.status == "dispatched"}
    return [t if t.status == "busy" or t.name not in on_job else Team(**{**asdict(t), "status": "busy"})
            for t in teams]


def needs(inc: Incident) -> dict[str, list[str]]:
    """Team types the facts call for: {"primary": [...], "secondary": [...], "why": [...]} (why = plain words)."""
    f = inc.facts
    deep = f.water_level in DEEP
    water_hazard = f.hazard in {"flood", "cyclone"} or f.water_level not in {None, "none"}
    stuck = (bool(f.trapped) or bool(f.on_roof)) and f.water_level != "none"  # trapped in a dry house: a crew, not a boat
    boat = (water_hazard and (deep or stuck)) or "boat" in f.needs
    medical = bool(f.injuries or f.medical_needs) or f.hazard == "medical" or "ambulance" in f.needs
    fire = f.hazard in {"fire", "building_collapse", "landslide"}
    why = []
    if deep:
        why.append(f"water {f.water_level}-high")
    if f.trapped:
        why.append("trapped")
    if f.on_roof:
        why.append("on a roof")
    if fire:
        why.append(f.hazard.replace("_", " "))
    if medical:
        why.append(", ".join(["injured" if x == "other" else x for x in f.injuries] + f.medical_needs)
                   or "medical help asked")
    primary, secondary = [], []
    if fire:
        primary.append("fire")
    if boat:
        primary.append("boat")
    if medical:
        (secondary if primary else primary).extend(["ambulance", "medical"])
    if not primary:  # no hazard yet (missed call) or a dry, uninjured report: fire & rescue is the general crew
        secondary.append("fire")
    return {"primary": primary, "secondary": secondary, "why": why}


def eta_minutes(km: float, speed_kmh: float) -> int:
    return round(MOBILISE_MIN + km * ROUTE_FACTOR / speed_kmh * 60)


def recommend(inc: Incident, teams, top: int | None = None) -> list[dict]:
    """Available teams ranked for this incident, best first, each with its score and plain-English reasons.
    ETA is from the team's base (the roster has no live positions)."""
    need = needs(inc)
    f = inc.facts
    people = f.people_count or 1
    out = []
    for t in teams:
        if t.status != "available":
            continue
        if t.type in {"ambulance", "medical"} and f.water_level in DEEP:
            continue  # cannot reach through deep water; a boat brings the patient out first
        reasons = []
        if t.type in need["primary"]:
            match, fit = 50, "matches"
        elif t.type in need["secondary"]:
            match, fit = 25, "also useful" if need["primary"] else "general rescue crew"
        else:
            continue  # wrong kind of team for this emergency
        reasons.append(TYPE_LABEL[t.type])
        cap = 15 if t.capacity >= people else round(15 * t.capacity / people)
        if inc.lat is None:
            km = eta = None
            time_pts = 0
            reasons.append("location unknown, no ETA")
        else:
            km = haversine_m((inc.lat, inc.lon), (t.lat, t.lon)) / 1000
            eta = eta_minutes(km, t.speed_kmh)
            time_pts = round(35 * max(0.0, 1 - eta / 60))
            reasons += [f"{km:.1f} km", f"~{eta} min"]
        if f.people_count is None:  # scored as one person, but never claimed to fit "everyone"
            reasons.append(f"carries {t.capacity}, people count unknown")
        else:
            reasons.append(f"fits {people} {'person' if people == 1 else 'people'}" if t.capacity >= people
                           else f"carries {t.capacity} of {people}, more trips needed")
        reasons += need["why"]
        out.append({"team_id": t.id, "team": t.name, "type": t.type, "base": t.base, "fit": fit,
                    "distance_km": None if km is None else round(km, 1), "eta_min": eta,
                    "eta": None if eta is None else f"~{eta} min", "capacity": t.capacity,
                    "score": match + cap + time_pts, "reasons": reasons, "summary": " · ".join(reasons)})
    out.sort(key=lambda r: (-r["score"], r["eta_min"] if r["eta_min"] is not None else 10**6, r["team_id"]))
    return out[:top] if top else out


def plan(incidents: list[Incident], teams) -> dict:
    """Greedy suggestion for every waiting incident: most severe first, then the one waiting longest; each takes
    its best free team and no team is used twice. Unlocated incidents are left for a callback, not guessed."""
    free = [t for t in teams if t.status == "available"]
    waiting = sorted((i for i in incidents if i.status == "new"), key=lambda i: (-i.severity.score, i.created_at))
    assignments, unassigned = [], []
    for inc in waiting:
        place = inc.facts.locality or inc.facts.landmark or "Unknown location"
        base = {"incident_id": inc.id, "place": place, "level": inc.severity.level, "score": inc.severity.score}
        if inc.lat is None:
            unassigned.append({**base, "reason": "location unknown: call back for a landmark before sending a team"})
            continue
        best = recommend(inc, free, top=1)
        if not best:
            unassigned.append({**base, "reason": "no suitable team free" if free else "every team is busy"})
            continue
        r = best[0]
        free = [t for t in free if t.id != r["team_id"]]
        assignments.append({**base, **{k: r[k] for k in ("team_id", "team", "type", "distance_km", "eta_min", "eta",
                                                       "summary")}})
    return {"assignments": assignments, "unassigned": unassigned, "teams_free": [t.name for t in free]}
