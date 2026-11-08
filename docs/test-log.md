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
