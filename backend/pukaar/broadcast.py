"""Multilingual broadcast alerts: one English alert -> translated in ONE LLM call -> spoken by Timbre per language."""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from voice_core.llm import parse_json_loose

from .data import Place
from .triage import LANG_NAMES

BROADCAST_LANGS = ["ta-IN", "hi-IN", "te-IN", "en-IN", "ml-IN", "kn-IN", "bn-IN"]


_SCRIPT = {"ta": r"[\u0B80-\u0BFF]", "hi": r"[\u0900-\u097F]", "mr": r"[\u0900-\u097F]", "te": r"[\u0C00-\u0C7F]",
           "kn": r"[\u0C80-\u0CFF]", "ml": r"[\u0D00-\u0D7F]", "bn": r"[\u0980-\u09FF]"}


def mask_places(text_en: str, places: list[Place]) -> tuple[str, dict[str, Place]]:
    """Replaces known place names with {P1}, {P2}... so the LLM cannot mistranslate them ("Aadhaar river" for Adyar)."""
    hits = []  # (position, place); longest names first so "Anna Nagar East" is not split
    taken = text_en
    for p in sorted(places, key=lambda p: -len(p.name)):
        m = re.search(rf"\b{re.escape(p.name)}\b", taken, re.I)
        if m:
            hits.append((m.start(), p))
            taken = taken[:m.start()] + "#" * len(m.group()) + taken[m.end():]
    found = {f"{{P{i}}}": p for i, (_, p) in enumerate(sorted(hits, key=lambda h: h[0]), 1)}
    for tok, p in sorted(found.items(), key=lambda kv: -len(kv[1].name)):
        text_en = re.sub(rf"\b{re.escape(p.name)}\b", tok, text_en, flags=re.I)
    return text_en, found


def unmask(text: str, found: dict[str, Place], lang: str) -> str:
    script = _SCRIPT.get(lang.split("-")[0])
    for tok, p in found.items():
        native = next((a for a in p.aliases if script and re.search(script, a)), p.name)
        text = text.replace(tok, native)
    return text


async def make_broadcast(text_en: str, langs: list[str], llm, tts: Callable[[str, str], Awaitable[str]],
                         places: list[Place] | None = None) -> list[dict]:
    """Returns [{lang, language, text, audio}] where audio is whatever `tts(text, lang)` returns (a cache key)."""
    others = [l for l in langs if not l.startswith("en")]
    masked, found = mask_places(text_en, places or [])
    translations: dict = {}
    if others:
        names = {l: LANG_NAMES[l.split("-")[0]] for l in others}
        try:
            raw = await llm.complete([
                {"role": "system", "content": "Translate this official disaster alert for the public. Return ONE JSON object "
                                              f"mapping each code to the translation in that language's own script: {json.dumps(names)}. "
                                              "Keep tokens like {P1} exactly as they are (they are place names). "
                                              "Keep numbers and instructions exact. Add nothing."},
                {"role": "user", "content": masked},
            ], temperature=0.2, max_tokens=900, json_mode=True)
            translations = parse_json_loose(raw)
        except Exception:
            translations = {}
    items = []
    for lang in langs:
        text = text_en if lang.startswith("en") else unmask(str(translations.get(lang) or "").strip(), found, lang)
        if text:
            items.append({"lang": lang, "language": LANG_NAMES[lang.split("-")[0]], "text": text, "audio": await tts(text, lang)})
    return items
