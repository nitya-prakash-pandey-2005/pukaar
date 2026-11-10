"""District situation report (SitRep): one page a district officer can read, print or forward.

Pure aggregation over the incident list; nothing is estimated. Vulnerable and trapped figures count incidents
(households), not people, because a caller reports "my mother is old", not a head count per category.
"""

from __future__ import annotations

import time
from collections import Counter

from .domain import Incident

LEVELS = ["critical", "high", "medium", "low"]
VULN_GROUPS = {"elderly": {"elderly"}, "children": {"child", "infant"}, "medical": {"sick", "pregnant"},
               "disabled": {"disabled"}}


def _place(i: Incident) -> str:
    return i.facts.locality or i.facts.landmark or "Unknown location"


def _clock(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))


def sitrep(incidents: list[Incident], calls: int, now: float, district: str = "Chennai") -> dict:
    open_ = [i for i in incidents if i.status != "resolved"]
    f = [i.facts for i in incidents]
    vulnerable = {k: sum(bool(set(x.vulnerable) & v) or (k == "medical" and bool(x.medical_needs or x.injuries))
                         for x in f) for k, v in VULN_GROUPS.items()}
    waits = sorted((now - i.created_at) / 60 for i in incidents if i.severity.level == "critical" and i.status == "new")
    by_place: dict[str, list[Incident]] = {}
    for i in incidents:
        by_place.setdefault(_place(i), []).append(i)
    hot = sorted(by_place.items(), key=lambda kv: (-len(kv[1]), -max(x.severity.score for x in kv[1]), kv[0]))
    timeline = []
    for i in incidents:
        n = i.facts.people_count
        who = "people count unknown" if not n else f"{n} {'person' if n == 1 else 'people'}"
        timeline.append({"t": i.created_at, "time": _clock(i.created_at),
                         "text": f"{i.severity.level.title()} {(i.facts.hazard or 'report').replace('_', ' ')} at "
                                 f"{_place(i)} ({who})"})
        if i.status == "dispatched" and i.dispatch:
            eta = f", ETA {i.dispatch['eta']}" if i.dispatch.get("eta") else ""
            timeline.append({"t": i.updated_at, "time": _clock(i.updated_at),
                             "text": f"{i.dispatch['team']} dispatched to {_place(i)}{eta}"})
        elif i.status == "resolved":
            timeline.append({"t": i.updated_at, "time": _clock(i.updated_at), "text": f"{_place(i)} resolved"})
    timeline.sort(key=lambda e: -e["t"])
    status = Counter(i.status for i in incidents)
    rep = {
        "district": district,
        "generated_at": now,
        "calls": calls,
        "incidents": len(incidents),
        "by_level": {lv: sum(i.severity.level == lv for i in incidents) for lv in LEVELS},
        "status": {"waiting": status["new"], "dispatched": status["dispatched"], "resolved": status["resolved"]},
        "people_affected": sum(i.facts.people_count or 1 for i in open_),
        "vulnerable": vulnerable,
        "trapped": sum(bool(x.trapped) for x in f),
        "on_roof": sum(bool(x.on_roof) for x in f),
        "critical_waiting": {"count": len(waits), "avg_min": round(sum(waits) / len(waits)) if waits else None,
                             "oldest_min": round(waits[-1]) if waits else None},
        "hotspots": [{"place": p, "incidents": len(xs), "people": sum(x.facts.people_count or 1 for x in xs),
                      "max_level": max(xs, key=lambda x: x.severity.score).severity.level} for p, xs in hot[:5]],
        "timeline": [{k: e[k] for k in ("time", "text")} for e in timeline[:10]],
    }
    rep["markdown"] = to_markdown(rep)
    return rep


def to_markdown(r: dict) -> str:
    cw = r["critical_waiting"]
    v = r["vulnerable"]
    lines = [
        f"# Situation report: {r['district']} floods",
        f"Generated {time.strftime('%d %b %Y %H:%M', time.localtime(r['generated_at']))} by Pukaar. "
        "Synthetic demo data.",
        "",
        "## Summary",
        f"- Calls answered: {r['calls']}",
        f"- Incidents: {r['incidents']} (critical {r['by_level']['critical']}, high {r['by_level']['high']}, "
        f"medium {r['by_level']['medium']}, low {r['by_level']['low']})",
        f"- Waiting {r['status']['waiting']} · dispatched {r['status']['dispatched']} · resolved {r['status']['resolved']}",
        f"- People affected (open incidents): {r['people_affected']}",
        f"- Households with: elderly {v['elderly']}, children {v['children']}, medical needs {v['medical']}, "
        f"disabled {v['disabled']}",
        f"- Trapped: {r['trapped']} · on a roof: {r['on_roof']}",
        "- Critical incidents waiting: " + (f"{cw['count']} (average {cw['avg_min']} min, oldest {cw['oldest_min']} min)"
                                            if cw["count"] else "none"),
        "",
        "## Hotspots by locality",
    ]
    lines += [f"- {h['place']}: {h['incidents']} incident{'s' if h['incidents'] != 1 else ''}, {h['people']} people, "
              f"worst {h['max_level']}" for h in r["hotspots"]] or ["- none"]
    lines += ["", "## Recent timeline"]
    lines += [f"- {e['time']} {e['text']}" for e in r["timeline"]] or ["- nothing yet"]
    lines += ["", "Severity is a fixed rule table over the facts callers gave; a human confirms every dispatch.", ""]
    return "\n".join(lines)
