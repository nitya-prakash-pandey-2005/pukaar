import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class Place:
    name: str
    aliases: list[str]
    lat: float
    lon: float


@dataclass(frozen=True)
class Guidance:
    id: str
    hazards: list[str]  # "any" matches every hazard
    when: list[str]     # condition tokens; "any" always matches
    text_en: str


@cache
def load_gazetteer() -> list[Place]:
    return [Place(**p) for p in json.loads((DATA / "gazetteer_chennai.json").read_text(encoding="utf-8"))]


@cache
def load_guidance() -> list[Guidance]:
    return [Guidance(**g) for g in json.loads((DATA / "guidance_kb.json").read_text(encoding="utf-8"))]
