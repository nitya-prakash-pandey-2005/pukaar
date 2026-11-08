"""LLM triage: extract facts from the call, and build the calm one-question reply prompt (design §6–8)."""

import json

from voice_core.llm import parse_json_loose
from voice_core.types import Turn

from .data import Guidance
from .domain import HAZARDS, INJURIES, MEDICAL, NEEDS, VULNERABLE, WATER_LEVELS, Facts, merge_facts

LANG_NAMES = {"ta": "Tamil", "hi": "Hindi", "te": "Telugu", "en": "English", "kn": "Kannada", "ml": "Malayalam",
              "bn": "Bengali", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi"}

EXTRACT_PROMPT = f"""You extract facts from a disaster helpline call. Return ONE JSON object with only these keys:
locality (area name, string), landmark (string), hazard (one of {sorted(HAZARDS)}), people_count (integer),
trapped (bool), on_roof (bool), water_level (one of {sorted(WATER_LEVELS)}), vulnerable (list from {sorted(VULNERABLE)}),
injuries (list from {sorted(INJURIES)}), medical_needs (list from {sorted(MEDICAL)}), needs (list from {sorted(NEEDS)}),
caller_language (BCP-47 code such as ta-IN).
Only include a key when the caller clearly said it; otherwise use null or []. Never guess or fill defaults:
water_level "none" only if the caller says there is no water; trapped and on_roof only if the caller says so.
Write place names in English letters."""

SLOT_QUESTIONS = {
    "location": "where they are: the area name and a nearby landmark",
    "people": "how many people are with them, and whether they are trapped",
    "injuries": "whether anyone is injured or needs medicine, oxygen or dialysis",
    "water_level": "how high the water has reached on their body",
    "vulnerable": "whether there are babies, children, elderly, pregnant, disabled or sick people with them",
}


def _transcript(history: list[Turn]) -> str:
    return "\n".join(f"{t.speaker}: {t.text}" for t in history[-12:])


async def extract_facts(llm, history: list[Turn], previous: Facts) -> Facts:
    """Returns previous facts merged with newly extracted ones; on any failure returns previous (never raises)."""
    try:
        known = previous.model_dump(exclude_none=True, exclude={"lat", "lon"})
        raw = await llm.complete([
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": f"Known facts: {json.dumps(known, ensure_ascii=False)}\n\nCall:\n{_transcript(history)}"},
        ], temperature=0.0, max_tokens=300, json_mode=True)
        d = parse_json_loose(raw)
        d.pop("lat", None), d.pop("lon", None)  # coordinates come from GPS / gazetteer only
        return merge_facts(previous, Facts.model_validate(d))
    except Exception:
        return previous


def _conditions(f: Facts) -> set[str]:
    c = {"any", *f.injuries, *f.medical_needs}
    if f.water_level:
        c.add(f.water_level)
    if f.on_roof:
        c.add("on_roof")
    if f.trapped:
        c.add("trapped")
    return c


def pick_guidance(f: Facts, kb: list[Guidance], already: set[str]) -> list[Guidance]:
    """At most 2 candidates for this hazard and situation; condition-specific entries before general ones."""
    cond = _conditions(f)
    ok = [g for g in kb if g.id not in already and set(g.when) & cond
          and ("any" in g.hazards or (f.hazard or "flood") in g.hazards)]
    return sorted(ok, key=lambda g: "any" in g.when)[:2]  # stable: keeps KB order within each group


def build_reply_messages(f: Facts, slot: str | None, guidance: list[Guidance], lang: str | None,
                         dispatcher_eta: str | None, history: list[Turn]) -> list[dict]:
    language = LANG_NAMES.get((lang or "en").split("-")[0], "the caller's language")
    ask = f"Then ask exactly ONE question: {SLOT_QUESTIONS[slot]}." if slot else "Do not ask a question; keep the line open."
    options = "\n".join(f"- {g.text_en} [[{g.id}]]" for g in guidance) or "- (none)"
    system = (
        f"You are Pukaar, a calm disaster helpline. Reply in {language}, in the caller's script (code-mixing is fine), "
        f"2-3 short sentences, in this order:\n"
        f"1. Reassure in 3-6 words, such as 'I am with you' or 'stay calm'. Do NOT say they are safe, and do NOT say "
        f"help is coming or on the way unless the ETA below is given.\n"
        f"2. Optionally, at most one instruction from this list: say it translated, then end that sentence with its id "
        f"in double brackets like [[FLD-03]]. Never write an id without saying the instruction.\n{options}\n"
        f"3. {ask}\n"
        f"Never invent advice. Never promise an arrival time unless the ETA is given: {dispatcher_eta or 'none'}.\n"
        f"Known facts: {json.dumps(f.model_dump(exclude_none=True), ensure_ascii=False)}"
    )
    msgs = [{"role": "system", "content": system}]
    msgs += [{"role": "assistant" if t.speaker == "pukaar" else "user", "content": t.text} for t in history[-10:]]
    return msgs
