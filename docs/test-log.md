# Test log

One line per test: date and time, build, scenario, result, latency, notes.

| When (IST) | Build | Scenario | Result | Latency | Notes |
|---|---|---|---|---|---|
| Sun 8 Nov 13:20 | feat/tm-pukaar-domain | Live call, real Gnani + Groq (`qwen/qwen3.8-27b`). Caller = 4 Tamil lines spoken by Timbre "Prakash", streamed at real-time pace into `/ws/call` | Works end to end | Prisma STT 90–133 ms; reply audio starts ~2.0 s after the caller stops | Exact Tamil transcripts; triage reached critical 84 on "water up to the chest"; each reply = reassurance + one approved instruction in Tamil + one question in slot order. (TM) |

## Findings (Sun 8 Nov, TM)

- First live run: replies said "you are safe" / "help is coming" before any dispatch, and extraction invented facts (`water_level: none`, `trapped: false`), which stopped Pukaar from ever asking about water. Fixed in the prompts (`triage.py`); re-verified live.
- The model sometimes wrote a `[[ID]]` without saying the instruction (logged as given). The prompt now forbids it and puts the instruction before the question.
- Reply latency ~2.0 s: Prisma end-of-speech + fact extraction (~0.45 s) + reply (~0.3 s) + first TTS chunk. Next win: pre-rendered fillers like Dadi's `assets.load_or_make_fillers`.
- Delete `cache/pukaar.db` before recording a demo: a new call within 300 m and 3 h merges into old test incidents (dedup working as designed).
| Sun 8 Nov 14:30 | feat/tm-pukaar-domain | Noise drill, 6 synthetic calls × {clean, 20, 10, 5, 0 dB} rain, Prisma REST `indic-auto` | Triage accuracy flat from clean to 0 dB | Same-script CER 7.5% clean → 10.8% at 0 dB | Results: `docs/drill-results.md`. Small sample; clean row = LLM extraction variance. (TM) |

## Drill findings (Sun 8 Nov, TM)

- **Noise barely hurts.** Locality 67%, vulnerable F1 100% and severity level 67% are identical at clean and 0 dB; Tamil transcripts stay at ~3–7% CER even at 0 dB.
- **Keyterm bias.** With only 10 demo localities as keyterms, Prisma heard "Velachery" in noise where the caller said another area (case 3, 10/5/0 dB). Fixed: all 42 gazetteer localities are keyterms now. Not re-measured yet (needs another drill run = Gnani credits).
- **Script mismatch.** The LLM sometimes wrote callers in romanised Hinglish/Tanglish; Prisma correctly writes Devanagari/Tamil. CER now skips cross-script pairs; the writing prompt now asks for native script.
- **Tamil place names.** Prisma wrote சோழிநல்லூர் correctly, but the LLM transliterated it to "Chozhinallur". Fixed: when the LLM spelling does not map to the gazetteer, Pukaar matches the caller's own words against the Tamil aliases.
