"""More ways in and out: SMS/WhatsApp intake (no voice call needed), dispatcher free-text messages relayed in the
caller's language, and CAP 1.2 XML for broadcast alerts (the format India's SACHET alert system consumes)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from voice_core.types import Turn

from .data import Guidance, Place
from .domain import Facts, Incident, locate, next_slot, resolve_locality
from .guard import adds_nothing, fallback, guard_reply
from .store import Store
from .triage import LANG_NAMES, build_reply_messages, extract_facts, pick_guidance

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
_SCRIPTS = (("ta-IN", r"[஀-௿]"), ("te-IN", r"[ఀ-౿]"), ("kn-IN", r"[ಀ-೿]"),
            ("ml-IN", r"[ഀ-ൿ]"), ("bn-IN", r"[ঀ-৿]"), ("hi-IN", r"[ऀ-ॿ]"))
IST = timezone(timedelta(hours=5, minutes=30))


def detect_lang(text: str) -> str:
    return next((code for code, rx in _SCRIPTS if re.search(rx, text or "")), "en-IN")


async def sms_intake(text: str, gps: tuple[float, float] | None, llm, store: Store, places: list[Place],
                     kb: list[Guidance]) -> tuple[Incident, str]:
    """One text message -> facts -> incident on the map (channel "text") + a guarded reply SMS."""
    lang = detect_lang(text)
    turn = Turn("caller", text, 0.0, lang)
    f = resolve_locality(await extract_facts(llm, [turn], Facts()), [text], places, gps)
    cid = store.create_call(lang)
    store.add_turn(cid, turn)
    inc = store.upsert_incident(cid, f, locate(f, places, gps), channel="text")
    cands = pick_guidance(f, kb, set())
    try:
        raw = await llm.complete(build_reply_messages(f, next_slot(f), cands, lang, None, [turn]),
                                 temperature=0.4, max_tokens=120)
    except Exception:
        raw = ""
    reply, ids = guard_reply(raw, {g.id for g in cands}, None, lang)
    if ids:
        store.add_guidance(cid, ids)
    store.add_turn(cid, Turn("pukaar", reply or fallback(lang), 0.0, lang))
    store.end_call(cid, 0.0)
    return store.get_incident(inc.id) or inc, reply or fallback(lang)


async def relay_line(llm, lang: str, text_en: str) -> str:
    """A dispatcher's own English words in the caller's language (translation only; nothing added)."""
    if lang.startswith("en"):
        return text_en
    try:
        out = (await llm.complete([
            {"role": "system", "content": f"Translate into {LANG_NAMES.get(lang.split('-')[0], 'the same language')} for a "
                                          "frightened caller. Keep names, numbers and times exactly. Output only the translation."},
            {"role": "user", "content": text_en},
        ], temperature=0.2, max_tokens=150)).strip()
    except Exception:
        return text_en
    # a translation that adds a time, a "you are safe" or a number is not sent: the dispatcher's own words go instead
    return out if out and adds_nothing(text_en, out) else text_en


def cap_xml(text_en: str, items: list[dict], *, area: str, identifier: str, sent: str | None = None,
            event: str = "Flood", status: str = "Exercise") -> str:
    """CAP 1.2 alert with one <info> per language. status stays "Exercise" until an authority issues it."""
    ET.register_namespace("", CAP_NS)
    q = lambda tag: f"{{{CAP_NS}}}{tag}"  # noqa: E731
    root = ET.Element(q("alert"))
    for tag, val in (("identifier", identifier), ("sender", "pukaar@district-eoc.example"),
                     ("sent", sent or datetime.now(IST).replace(microsecond=0).isoformat()), ("status", status),
                     ("msgType", "Alert"), ("scope", "Public")):
        ET.SubElement(root, q(tag)).text = val
    for it in items:
        info = ET.SubElement(root, q("info"))
        for tag, val in (("language", it["lang"]), ("category", "Met"), ("event", event), ("urgency", "Immediate"),
                         ("severity", "Severe"), ("certainty", "Likely"), ("headline", text_en[:120]),
                         ("description", it["text"])):
            ET.SubElement(info, q(tag)).text = val
        ET.SubElement(ET.SubElement(info, q("area")), q("areaDesc")).text = area
    return ET.tostring(root, encoding="unicode", xml_declaration=False)
