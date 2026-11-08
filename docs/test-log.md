# Test log

One line per test: date and time, build, scenario, result, latency, notes.

| When (IST) | Build | Scenario | Result | Latency | Notes |
|---|---|---|---|---|---|
| Sun 8 Nov 13:20 | feat/tm-pukaar-domain | Live call, real Gnani + Groq (`qwen/qwen3.8-27b`). Caller = 4 Tamil lines spoken by Timbre "Prakash", streamed at real-time pace into `/ws/call` | Works end to end | Prisma STT 90–133 ms; reply audio starts ~2.0 s after the caller stops | Exact Tamil transcripts; triage reached critical 84 on "water up to the chest"; each reply = reassurance + one approved instruction in Tamil + one question in slot order. (TM) |
| Sun 8 Nov 14:30 | feat/tm-pukaar-domain | Noise drill, 6 synthetic calls × {clean, 20, 10, 5, 0 dB} rain, Prisma REST `indic-auto` | Triage accuracy flat from clean to 0 dB | Same-script CER 7.5% clean → 10.8% at 0 dB | Results: `docs/drill-results.md`. Small sample; clean row = LLM extraction variance. (TM) |

## Findings (Sun 8 Nov, TM)

- First live run: replies said "you are safe" / "help is coming" before any dispatch, and extraction invented facts (`water_level: none`, `trapped: false`), which stopped Pukaar from ever asking about water. Fixed in the prompts (`triage.py`); re-verified live.
- The model sometimes wrote a `[[ID]]` without saying the instruction (logged as given). The prompt now forbids it and puts the instruction before the question.
- Reply latency ~2.0 s: Prisma end-of-speech + fact extraction (~0.45 s) + reply (~0.3 s) + first TTS chunk. Next win: pre-rendered fillers like Dadi's `assets.load_or_make_fillers`.
- Delete `cache/pukaar.db` before recording a demo: a new call within 300 m and 3 h merges into old test incidents (dedup working as designed).

## Drill findings (Sun 8 Nov, TM)

- **Noise barely hurts.** Locality 67%, vulnerable F1 100% and severity level 67% are identical at clean and 0 dB; Tamil transcripts stay at ~3–7% CER even at 0 dB.
- **Keyterm bias.** With only 10 demo localities as keyterms, Prisma heard "Velachery" in noise where the caller said another area (case 3, 10/5/0 dB). Fixed: all 42 gazetteer localities are keyterms now. Not re-measured yet (needs another drill run = Gnani credits).
- **Script mismatch.** The LLM sometimes wrote callers in romanised Hinglish/Tanglish; Prisma correctly writes Devanagari/Tamil. CER now skips cross-script pairs; the writing prompt now asks for native script.
- **Tamil place names.** Prisma wrote சோழிநல்லூர் correctly, but the LLM transliterated it to "Chozhinallur". Fixed: when the LLM spelling does not map to the gazetteer, Pukaar matches the caller's own words against the Tamil aliases.
- **Groq budget per live turn (measured):** extraction ~530 tokens + reply ~470 tokens ≈ 1,000 tokens. One live call (4–6 turns/min) fits the free tier's 8k tokens/min; two simultaneous live calls, or a `fresh` surge during a call, do not. The default surge replays a recording (0 tokens).

## Sun 8 Nov night, branch `dilavesh` (TM)
- **Guard gap found and fixed:** "10 நிமிஷத்துல வருவோம்" (colloquial Tamil "we'll come in 10 minutes") passed the time-promise guard, which only knew min/मिनट/நிமிட. Now any minutes/hours word in Tamil, Hindi, Telugu, Kannada, Bengali, Malayalam or English, plus "coming soon" promises, triggers the safe fallback unless a dispatcher gave an ETA. Applies to live calls too.
- **SMS / WhatsApp intake (live, Groq only):** Tamil SMS (Velachery, 4 on the roof, chest-deep water, paati needs insulin) → text incident, **critical 84**, GPS + gazetteer; Hindi SMS (Saidapet, 3 people, waist-deep, sick child) → **high 57**, located by landmark; reply asks the next missing fact with approved guidance.
- **Dispatcher message relay (live):** "The boat is at the temple gate. Wave a white cloth." → "படகு கோவில் வாயிலில் உள்ளது. வெள்ளை துண்டை அசைக்கவும்." / "नौका मंदिर के द्वार पर है। सफेद कपड़ा लहराएँ।" (queued as callbacks because the SMS callers are not on a live call).
- **CAP 1.2 export:** broadcast alerts download as CAP XML (one `<info>` per language, status "Exercise"), the format India's SACHET alert platform uses.
