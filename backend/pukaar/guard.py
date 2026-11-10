"""Reply guardrail: only approved guidance ids, and no arrival time unless a dispatcher gave one."""

import re

FALLBACK = {
    "en": "Help is being arranged. Please stay on a high, dry place.",
    "hi": "मदद की व्यवस्था की जा रही है। कृपया किसी ऊँची, सूखी जगह पर रहिए।",
    "ta": "உதவி ஏற்பாடு செய்யப்படுகிறது. தயவுசெய்து உயரமான, உலர்ந்த இடத்தில் இருங்கள்.",
    "te": "సహాయం ఏర్పాటు చేస్తున్నాం. దయచేసి ఎత్తైన, పొడి ప్రదేశంలో ఉండండి.",
}
_ID_RE = re.compile(r"\[\[\s*([A-Z]{3}-\d{2})\s*\]\]")
_ANY_TAG_RE = re.compile(r"\[\[.*?\]\]")
_TIME_RE = re.compile(  # any time span or "soon" promise, in words or digits, in any script we serve
    r"\d+\s*(min|minute|मिनट|நிமிட)|jaldi pahunch|reaching soon|coming soon|जल्दी पहुँच|जल्दी आ|வந்துவிடும்"
    r"|\b(minutes?|mins?|hours?|hrs?|ghant[ae]?|ghanton|minat)\b|मिनट|मिनिट|घंट|நிமிட|நிமிஷ|மணி\s*நேர"
    r"|నిమిష|గంట|ನಿಮಿಷ|ಗಂಟೆ|মিনিট|ঘণ্টা|മിനിറ്റ|മണിക്കൂ",
    re.IGNORECASE)
# false reassurance (design §4): nobody on the line can know the caller is safe, ETA or not
_SAFE_RE = re.compile(
    r"\byou(?:'re| are|'ll be| will be)(?: now| completely)? (?:safe|fine|out of danger)\b"
    r"|\baap (?:ab )?(?:safe|surakshit) (?:hain|ho)\b|आप (?:अब )?सुरक्षित (?:हैं|हो)"
    r"|பாதுகாப்பா(?:க)? இருக்கீங்க|பாதுகாப்பாக இருக்கிறீர்கள்|సురక్షితంగా ఉన్నారు",
    re.IGNORECASE)


def fallback(lang: str | None) -> str:
    return FALLBACK.get((lang or "en").split("-")[0], FALLBACK["en"])


def guard_reply(text: str, allowed_ids: set[str], eta: str | None, lang: str | None = None) -> tuple[str, list[str]]:
    """Returns (speakable text with [[ID]] tags removed, ids used), or the safe fallback line."""
    ids = _ID_RE.findall(text)
    bad_tag = len(ids) != len(_ANY_TAG_RE.findall(text))
    if (bad_tag or any(i not in allowed_ids for i in ids) or (eta is None and _TIME_RE.search(text))
            or _SAFE_RE.search(text)):
        return fallback(lang), []
    return re.sub(r"\s{2,}", " ", _ANY_TAG_RE.sub("", text)).strip(), ids
