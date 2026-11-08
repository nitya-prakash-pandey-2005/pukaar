"""Noise drill: synthetic distress calls spoken by Timbre, buried in rain at 8 kHz, transcribed by Prisma, then triaged.

Reference = facts extracted from the exact words; so the score measures only what noise + speech-to-text lose.
"""

from __future__ import annotations

import asyncio
import random
import re
from difflib import SequenceMatcher

from voice_core.audio import float_to_pcm16, mix_at_snr, pcm16_to_float, telephone_band, wav_bytes
from voice_core.config import Settings
from voice_core.gnani import TtsCache, transcribe_rest, tts_rest
from voice_core.types import Turn

from .assets import rain_noise
from .data import Place
from .domain import KEYTERMS, Facts, _match, resolve_locality, score
from .sim import make_case, utterance_prompt
from .triage import extract_facts

SNRS = (None, 20, 10, 5, 0)
METRICS = ("cer", "locality", "people", "water_level", "vulnerable_f1", "severity_level")


class RetryLLM:
    """Retries LLM calls (Groq free tier: 8k tokens/min), so a 429 is never scored as a wrong answer."""

    def __init__(self, llm, tries: int = 5, wait: float = 15.0):
        self.llm, self.tries, self.wait = llm, tries, wait

    async def complete(self, messages, **kw) -> str:
        for i in range(self.tries):
            try:
                return await self.llm.complete(messages, **kw)
            except Exception:
                if i == self.tries - 1:
                    raise
                await asyncio.sleep(self.wait)
        return ""


def _norm(s: str) -> str:
    return re.sub(r"[\s.,!?;:'\"।()\-]", "", (s or "").casefold())


_SCRIPTS = {"latin": r"[A-Za-z]", "devanagari": r"[\u0900-\u097F]", "tamil": r"[\u0B80-\u0BFF]", "telugu": r"[\u0C00-\u0C7F]"}


def script_of(s: str) -> str:
    return max(_SCRIPTS, key=lambda k: len(re.findall(_SCRIPTS[k], s or "")))


def cer(ref: str, hyp: str) -> float | None:
    """Character error rate, ignoring case, spaces and punctuation. None when the two are in different scripts
    (romanised Hinglish vs Prisma's Devanagari is not an error)."""
    if hyp and script_of(ref) != script_of(hyp):
        return None
    r, h = _norm(ref), _norm(hyp)
    if not r:
        return 0.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return round(min(1.0, prev[-1] / len(r)), 4)


def same_locality(a: str | None, b: str | None, places: list[Place] | None = None) -> bool:
    """Same gazetteer place, or spellings ≥ 80% alike (LLM transliteration varies between runs)."""
    if not a or not b:
        return not a and not b
    if places and (ma := _match(a, places)) and (mb := _match(b, places)):
        return ma[0].name == mb[0].name
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio() >= 0.8


def score_case(ref: Facts, got: Facts, places: list[Place] | None = None) -> dict:
    rv, gv = set(ref.vulnerable), set(got.vulnerable)
    tp = len(rv & gv)
    f1 = 1.0 if not rv and not gv else (2 * tp / (len(rv) + len(gv)))
    return {
        "locality": same_locality(ref.locality, got.locality, places),
        "people": ref.people_count == got.people_count,
        "water_level": ref.water_level == got.water_level,
        "vulnerable_f1": f1,
        "severity_level": score(ref).level == score(got).level,
    }


def summarise(rows: list[dict]) -> dict:
    def group(key):
        out: dict[str, dict] = {}
        for k in dict.fromkeys(("clean" if r[key] is None else str(r[key])) for r in rows):
            g = [r for r in rows if ("clean" if r[key] is None else str(r[key])) == k]
            c = [r["cer"] for r in g if r["cer"] is not None]
            out[k] = {"n": len(g), "n_cer": len(c), "cer": round(sum(c) / len(c), 3) if c else None,
                      **{m: round(sum(float(r[m]) for r in g) / len(g), 3) for m in METRICS if m != "cer"}}
        return out
    return {"by_snr": group("snr"), "by_lang": group("lang")}


def _facts(f: Facts) -> dict:
    return f.model_dump(exclude_none=True, exclude_defaults=True)


async def rescore(rows: list[dict], llm, places: list[Place]) -> dict:
    """Re-extracts facts from saved transcripts (LLM only, no Gnani credits) and re-scores every row."""
    refs: dict[int, Facts] = {}
    out = []
    for r in rows:
        gps = tuple(r["gps"]) if r.get("gps") else None
        if r["case"] not in refs:
            refs[r["case"]] = resolve_locality(await extract_facts(llm, [Turn("caller", r["ref"], 0.0, r["lang"])], Facts()),
                                               [r["ref"]], places, gps)
        ref = refs[r["case"]]
        got = resolve_locality(await extract_facts(llm, [Turn("caller", r["hyp"], 0.0, r["lang"])], Facts()), [r["hyp"]], places, gps)
        out.append({**r, "cer": cer(r["ref"], r["hyp"]), "ref_facts": _facts(ref), "got_facts": _facts(got), **score_case(ref, got, places)})
    return {"rows": out, "summary": summarise(out)}


async def run_drill(n: int, snrs, settings: Settings, llm, emit, rng: random.Random, places: list[Place],
                    tts_fn=tts_rest, stt_fn=transcribe_rest) -> dict:
    """One API call at a time. TTS is cached, so re-runs only pay for speech-to-text."""
    sr = 8000
    cache = TtsCache(settings.cache_dir)
    rain = rain_noise(30.0, sr, seed=7)
    key = settings.gnani_api_key
    rows: list[dict] = []
    for i in range(n):
        c = make_case(rng, places)
        text = (await llm.complete(utterance_prompt(c), temperature=0.9, max_tokens=150)).strip()
        ref = resolve_locality(await extract_facts(llm, [Turn("caller", text, 0.0, c.lang)], Facts()), [text], places, c.gps)
        kw = dict(voice=c.voice, language=c.lang, sample_rate=sr)
        k = cache.key(text, **kw)
        pcm = cache.get(k)
        if pcm is None:
            pcm = await tts_fn(key, text, **kw)
            cache.put(k, pcm)
        phone = telephone_band(pcm16_to_float(pcm), sr)
        for snr in snrs:
            x = phone if snr is None else mix_at_snr(phone, rain[rng.randrange(len(rain) // 2):], snr)
            ev = await stt_fn(key, wav_bytes(float_to_pcm16(x), sr), language_code="indic-auto", keyterms=KEYTERMS)
            got = resolve_locality(await extract_facts(llm, [Turn("caller", ev.text, 0.0, c.lang)], Facts()), [ev.text], places, c.gps)
            row = {"case": i, "lang": c.lang, "voice": c.voice, "snr": snr, "gps": list(c.gps), "ref": text, "hyp": ev.text,
                   "cer": cer(text, ev.text), "ref_facts": _facts(ref), "got_facts": _facts(got), **score_case(ref, got, places)}
            rows.append(row)
            await emit({"type": "drill_row", **row})
    return {"rows": rows, "summary": summarise(rows)}
