"""SQLite persistence: calls, turns, incidents (with dedup) and queued voice callbacks."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from voice_core.types import Turn

from .domain import Facts, Incident, merge_facts, score, should_merge

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
  id TEXT PRIMARY KEY, lang TEXT, started_at REAL, ended_at REAL, seconds REAL DEFAULT 0,
  incident_id TEXT, reply_s REAL DEFAULT 0, replies INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT, speaker TEXT, text TEXT, t REAL, lang TEXT, latency_ms REAL
);
CREATE INDEX IF NOT EXISTS turns_call ON turns(call_id);
CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, status TEXT, updated_at REAL, data TEXT);
CREATE TABLE IF NOT EXISTS callbacks (id TEXT PRIMARY KEY, call_id TEXT, text TEXT, lang TEXT, created_at REAL);
"""


def _id() -> str:
    return uuid.uuid4().hex[:12]


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def _exec(self, sql: str, args: tuple = ()) -> None:
        self.db.execute(sql, args)
        self.db.commit()

    # ------------------------------------------------------------------ calls
    def create_call(self, lang: str) -> str:
        cid = _id()
        self._exec("INSERT INTO calls(id, lang, started_at) VALUES (?,?,?)", (cid, lang, time.time()))
        return cid

    def set_lang(self, call_id: str, lang: str) -> None:
        self._exec("UPDATE calls SET lang=? WHERE id=?", (lang, call_id))

    def call_lang(self, call_id: str) -> str:
        row = self.db.execute("SELECT lang FROM calls WHERE id=?", (call_id,)).fetchone()
        return (row and row["lang"]) or "en-IN"

    def end_call(self, call_id: str, seconds: float) -> None:
        self._exec("UPDATE calls SET ended_at=?, seconds=? WHERE id=?", (time.time(), float(seconds), call_id))

    def add_reply_latency(self, call_id: str, seconds: float) -> None:
        self._exec("UPDATE calls SET reply_s=reply_s+?, replies=replies+1 WHERE id=?", (seconds, call_id))

    def add_turn(self, call_id: str, turn: Turn) -> None:
        self._exec("INSERT INTO turns(call_id, speaker, text, t, lang, latency_ms) VALUES (?,?,?,?,?,?)",
                   (call_id, turn.speaker, turn.text, turn.t, turn.lang, turn.latency_ms))

    def get_call(self, call_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["turns"] = [dict(r) for r in self.db.execute(
            "SELECT speaker, text, t, lang, latency_ms FROM turns WHERE call_id=? ORDER BY id", (call_id,))]
        return d

    def recent_caller_call(self, text: str, since: float) -> str | None:
        """The latest call since `since` in which the caller said exactly `text` (case and spacing ignored)."""
        norm = " ".join(text.split()).casefold()
        rows = self.db.execute("SELECT t.call_id, t.text FROM turns t JOIN calls c ON c.id = t.call_id "
                               "WHERE t.speaker = 'caller' AND c.started_at >= ? ORDER BY t.id DESC", (since,))
        return next((r["call_id"] for r in rows if " ".join(r["text"].split()).casefold() == norm), None)

    # ------------------------------------------------------------------ incidents
    def _save(self, inc: Incident) -> Incident:
        self._exec("INSERT OR REPLACE INTO incidents(id, status, updated_at, data) VALUES (?,?,?,?)",
                   (inc.id, inc.status, inc.updated_at, inc.model_dump_json()))
        return inc

    def get_incident(self, incident_id: str | None) -> Incident | None:
        row = self.db.execute("SELECT data FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return Incident.model_validate_json(row["data"]) if row else None

    def list_incidents(self, status: str | None = None) -> list[Incident]:
        rows = self.db.execute("SELECT data FROM incidents" + (" WHERE status=?" if status else ""),
                               (status,) if status else ()).fetchall()
        incs = [Incident.model_validate_json(r["data"]) for r in rows]
        return sorted(incs, key=lambda i: (-i.severity.score, i.created_at))

    def _link(self, call_id: str, incident_id: str) -> None:
        self._exec("UPDATE calls SET incident_id=? WHERE id=?", (incident_id, call_id))

    def upsert_incident(self, call_id: str, facts: Facts, loc: tuple | None, channel: str = "voice") -> Incident:
        """loc = locate() output (lat, lon, source, confidence) or None. Merges duplicates (design §7)."""
        now = time.time()
        row = self.db.execute("SELECT incident_id FROM calls WHERE id=?", (call_id,)).fetchone()
        own = self.get_incident(row["incident_id"] if row else None)
        near = (loc[0], loc[1]) if loc and loc[2] != "landmark" else None  # a gazetteer centre is not a position

        def find_other() -> Incident | None:
            return next((i for i in self.list_incidents() if i.id != (own and own.id)
                         and should_merge(i, facts, near, now)), None)

        if own and own.call_ids == [call_id]:  # this caller's own pin: update it, unless it now duplicates another
            target = find_other()
            if target is None:
                own.facts, own.severity, own.updated_at = facts, score(facts), now
                if loc:
                    own.lat, own.lon, own.loc_source, own.loc_confidence = loc
                return self._save(own)
            self._exec("DELETE FROM incidents WHERE id=?", (own.id,))
            target.guidance_given = list(dict.fromkeys(target.guidance_given + own.guidance_given))
        else:
            target = own or find_other()

        if target is None:
            inc = Incident(id=_id(), call_ids=[call_id], facts=facts, severity=score(facts), channel=channel,
                           created_at=now, updated_at=now)
            if loc:
                inc.lat, inc.lon, inc.loc_source, inc.loc_confidence = loc
            self._link(call_id, inc.id)
            return self._save(inc)

        target.facts = merge_facts(target.facts, facts)
        target.severity, target.updated_at = score(target.facts), now
        if call_id not in target.call_ids:
            target.call_ids.append(call_id)
        if target.lat is None and loc:
            target.lat, target.lon, target.loc_source, target.loc_confidence = loc
        self._link(call_id, target.id)
        return self._save(target)

    def add_guidance(self, call_id: str, ids: list[str]) -> None:
        row = self.db.execute("SELECT incident_id FROM calls WHERE id=?", (call_id,)).fetchone()
        inc = self.get_incident(row["incident_id"] if row else None)
        if inc and ids:
            inc.guidance_given = list(dict.fromkeys(inc.guidance_given + ids))
            self._save(inc)

    def dispatch(self, incident_id: str, team: str, note: str, eta: str | None) -> Incident | None:
        inc = self.get_incident(incident_id)
        if inc:
            inc.status, inc.dispatch, inc.updated_at = "dispatched", {"team": team, "note": note, "eta": eta}, time.time()
            self._save(inc)
        return inc

    def resolve(self, incident_id: str) -> Incident | None:
        inc = self.get_incident(incident_id)
        if inc:
            inc.status, inc.updated_at = "resolved", time.time()
            self._save(inc)
        return inc

    # ------------------------------------------------------------------ callbacks + KPIs
    def queue_callback(self, call_id: str, text: str, lang: str) -> str:
        cb = _id()
        self._exec("INSERT INTO callbacks(id, call_id, text, lang, created_at) VALUES (?,?,?,?,?)",
                   (cb, call_id, text, lang, time.time()))
        return cb

    def pending_callbacks(self, call_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT id, text, lang, created_at FROM callbacks WHERE call_id=? ORDER BY created_at", (call_id,))]

    def kpis(self) -> dict:
        c = self.db.execute("SELECT COUNT(*) n, SUM(reply_s) s, SUM(replies) r FROM calls").fetchone()
        open_ = [i for i in self.list_incidents() if i.status != "resolved"]
        return {
            "calls": c["n"],
            "avg_answer_s": round(c["s"] / c["r"], 2) if c["r"] else None,  # LLM time to first reply sentence
            "critical_open": sum(i.severity.level == "critical" for i in open_),
            "people_affected": sum(i.facts.people_count or 1 for i in open_),
        }
