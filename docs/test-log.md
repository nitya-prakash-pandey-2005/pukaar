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

## Tue 10 Nov 18:55–19:05, `main`, live product screenshots (CL)
- **Setup:** real Gnani + Groq (`qwen/qwen3.8-27b`), fresh `cache/pukaar.db`. Caller = 3 Tamil lines spoken by Timbre "Prakash" (Velachery bus stop, 4 people on the roof, chest-deep water, 80-year-old grandmother needs insulin, a small child), played into Chrome's fake microphone in real time; 3 calls.
- **Calls:** Prisma wrote every line in Tamil script with the meaning intact (e.g. நாங்க → நாங்கள்). Severity reached critical 90 (flood 20, chest 30, roof 10, elderly + child 14, insulin 10, 4 people 6). Calls 2 and 3 merged into the call-1 incident (4 callers with one surge caller). Control-room "average reply time" (LLM time to first reply sentence) 0.72–1.05 s. The last reply of calls 2 and 3 was the safe Tamil fallback line (used when the LLM reply is empty, fails or is blocked; the log does not say which).
- **SMS:** Tamil SMS (Mudichur, 5 on a roof, waist-deep, pregnant woman) → high 68, located, Tamil reply asking about injuries and medicines. **Finding (fixed after the run, re-checked with unit tests only):** a romanised-Hindi SMS ("Saidapet bridge ke paas hum 3 log hain, paani kamar tak…") was stored as `ta-IN` and answered in Tamil: `detect_lang` returns `en-IN` for Latin script, so the language comes from the LLM's `caller_language`, which said Tamil for a Chennai locality. Fix: `romanised_lang()` checks common romanised Hindi and Tamil words (2+ hits and a clear lead) before the LLM's guess (2 tests).
- **Dispatch / broadcast / CAP:** Mudichur dispatched (NDRF Boat 1, ETA 40 min). Broadcast in Tamil, Hindi, Telugu, English rendered by Timbre (MP3); Tamil kept அடையாறு, Hindi and Telugu kept "Adyar", "Kotturpuram", "Saidapet" in Latin script. CAP 1.2 XML downloaded. No 429s in the server log.
- **UI fix:** at 390 px the top-bar subtitle ran under the "Gnani live" pill; it now ends with an ellipsis.
- Screenshots: `docs/screenshots/product/`. About 45 Gnani requests in total (3 calls, 2 broadcasts, callers' audio, fillers).
