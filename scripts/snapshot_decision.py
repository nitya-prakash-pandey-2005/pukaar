"""Static-demo snapshots of the decision-support GETs, from the demo's own recorded incidents.

    uv run python scripts/snapshot_decision.py

Reads frontend/demo/api/incidents.json and kpis.json (written by scripts/snapshot_demo.py, which also calls this at
the end) and writes /api/teams, /api/plan, /api/sitrep, /api/hotspots and /api/incidents/{id}/recommend as JSON under
frontend/demo/api/. Pure functions only: no network, no keys, no LLM. The report time is the moment of the last
recorded update, so waiting times read as they stood at the end of the run.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict

from voice_core.config import repo_root

from pukaar.allocate import live_status, load_teams, plan, recommend
from pukaar.domain import Incident
from pukaar.hotspots import hotspots
from pukaar.sitrep import sitrep

API = repo_root() / "frontend" / "demo" / "api"


def write(rel: str, data) -> None:
    p = API / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    incs = [Incident.model_validate(i) for i in json.loads((API / "incidents.json").read_text(encoding="utf-8"))]
    calls = json.loads((API / "kpis.json").read_text(encoding="utf-8"))["calls"]
    now = max((i.updated_at for i in incs), default=0.0)
    roster = load_teams()
    teams = live_status(roster, incs)
    # roster_status lets the demo recompute "busy" after a dispatcher acts in the browser (src/demo/demo.js)
    write("teams.json", [{**asdict(t), "roster_status": r.status} for t, r in zip(teams, roster, strict=True)])
    write("plan.json", plan(incs, teams))
    write("sitrep.json", sitrep(incs, calls, now))
    write("hotspots.json", hotspots(incs))
    for i in incs:
        write(f"incidents/{i.id}/recommend.json", {"incident_id": i.id, "recommendations": recommend(i, teams, top=3),
                                                   "teams_free": sum(t.status == "available" for t in teams)})
    print(f"decision snapshots: {len(incs)} incidents, {len(roster)} teams -> {API.relative_to(repo_root())}")


if __name__ == "__main__":
    sys.exit(main())
