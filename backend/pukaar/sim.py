"""Synthetic distress calls: ground-truth cases, caller utterances written by the LLM, and the surge replay."""

from __future__ import annotations

import asyncio
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from voice_core.types import Turn

from .data import Place
from .domain import Facts, locate, resolve_locality
from .store import Store
from .triage import LANG_NAMES, extract_facts

LANGS = ["ta-IN", "ta-IN", "hi-IN", "en-IN", "te-IN"]  # Chennai: mostly Tamil/Tanglish, migrant Hindi, Telugu
V3_VOICES = ["Shivani", "Lakshmi", "Kalpana", "Chetana", "Vasudha", "Riyaa", "Tarika",
             "Avinash", "Prakash", "Harshad", "Devansh", "Shubham", "Yashraj"]


@dataclass(frozen=True)
class Case:
    truth: Facts
    gps: tuple[float, float]
    lang: str
    voice: str


def _jitter(lat: float, lon: float, rng: random.Random, metres: float) -> tuple[float, float]:
    r, a = metres * math.sqrt(rng.random()) / 111_000, rng.random() * 2 * math.pi
    return round(lat + r * math.cos(a), 6), round(lon + r * math.sin(a) / math.cos(math.radians(lat)), 6)


def make_case(rng: random.Random, places: list[Place], near: Case | None = None) -> Case:
    """A random flood-night caller. `near` = another caller from the same spot (tests dedup)."""
    if near:
        place = next(p for p in places if p.name == near.truth.locality)
        gps, hazard = _jitter(*near.gps, rng, 80), near.truth.hazard
    else:
        place = rng.choice(places)
        gps, hazard = _jitter(place.lat, place.lon, rng, 150), rng.choices(["flood", "medical", "fire"], [8, 1, 1])[0]
    water = rng.choice(["ankle", "knee", "waist", "chest"]) if hazard == "flood" else "none"
    truth = Facts(
        locality=place.name, hazard=hazard, people_count=rng.randint(1, 8), water_level=water,
        on_roof=water in ("waist", "chest") and rng.random() < 0.6, trapped=rng.random() < 0.3,
        vulnerable=rng.sample(["infant", "child", "elderly", "pregnant", "disabled", "sick"], rng.choice([0, 0, 1, 2])),
        medical_needs=rng.sample(["oxygen", "insulin", "dialysis", "medication"], rng.choice([0, 0, 0, 1])),
    )
    return Case(truth, gps, rng.choice(LANGS), rng.choice(V3_VOICES))


def utterance_prompt(c: Case) -> list[dict]:
    lang = LANG_NAMES[c.lang.split("-")[0]]
    facts = c.truth.model_dump(exclude_none=True, exclude_defaults=True)
    return [
        {"role": "system", "content": f"You write what a frightened flood-night caller in Chennai says to a helpline, in "
                                      f"{lang} as people really speak it (code-mixing with English is fine, use the "
                                      f"native script). 1-3 short sentences, no quotes, no narration. Mention every fact "
                                      f"given, in your own words. Synthetic data only: no real names or numbers. Hindi and Telugu in their own script; "
                                      f"if the language is English, write plain English."},
        {"role": "user", "content": f"Facts: {facts}"},
    ]


async def _ingest(store: Store, places: list[Place], emit, lang: str, gps, text: str, f: Facts) -> None:
    cid = store.create_call(lang)
    store.add_turn(cid, Turn("caller", text, 0.0, lang))
    inc = store.upsert_incident(cid, f, locate(f, places, tuple(gps)), channel="text")
    store.end_call(cid, 0.0)
    await emit({"type": "incident", "incident": inc.model_dump(), "synthetic": True})
    await emit({"type": "kpis", **store.kpis()})


async def run_surge(n: int, llm, store: Store, places: list[Place], emit, rng: random.Random, delay: float = 2.5,
                    dup_rate: float = 0.3, record: Path | None = None, retry_wait: float = 8.0) -> dict:
    """Synthetic text callers through the real triage (LLM only, no Gnani credits). Saves a replayable recording."""
    cases: list[Case] = []
    rows: list[dict] = []
    for _ in range(n):
        c = make_case(rng, places, near=rng.choice(cases) if cases and rng.random() < dup_rate else None)
        cases.append(c)
        text, f = "", Facts()
        for attempt in range(2):  # one retry: Groq free tier allows 8k tokens/min
            if attempt:
                await asyncio.sleep(retry_wait)
            try:
                text = text or (await llm.complete(utterance_prompt(c), temperature=0.9, max_tokens=150)).strip()
            except Exception:
                continue
            if text and (f := await extract_facts(llm, [Turn("caller", text, 0.0, c.lang)], Facts())) != Facts():
                break
        if not text or f == Facts():
            continue
        f = resolve_locality(f, [text], places, c.gps)
        rows.append({"lang": c.lang, "gps": list(c.gps), "text": text, "facts": f.model_dump()})
        await _ingest(store, places, emit, c.lang, c.gps, text, f)
        await asyncio.sleep(delay)
    if record and rows:
        record.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"calls": len(rows), "incidents": len(store.list_incidents())}


async def replay_surge(rows: list[dict], store: Store, places: list[Place], emit, delay: float = 1.0) -> dict:
    """Replays a recorded surge (texts and the facts the real triage extracted) with no LLM calls."""
    for r in rows:
        await _ingest(store, places, emit, r["lang"], r["gps"], r["text"], Facts(**r["facts"]))
        await asyncio.sleep(delay)
    return {"calls": len(rows), "incidents": len(store.list_incidents())}
