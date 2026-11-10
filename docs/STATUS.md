# Task board: pukaar

Claim a task before starting: owner and branch, then push this file. A claim with no pushed progress for 3 hours can be taken over (note it here).
Owners: **NP** = Nitya · **TM** = teammate (plus AI assistant) · **CL** = Claude on Nitya's laptop.
Plan: `docs/03-build-plan.md`. Engine contract: `voice-core/README.md` (the engine is built in `dadi-vs-scammers` first; sync it before Task 2).

| # | Task | Owner | Branch | Status |
|---|---|---|---|---|
| 0 | Bootstrap | CL | main | done (workspace, frontend copy, engine sync) |
| 1 | Data: gazetteer + guidance KB | TM | feat/tm-pukaar-domain | done |
| 2 | Domain: severity, locate, dedup, slots | TM | feat/tm-pukaar-domain | done |
| 3 | Triage extraction + reply guardrails | TM | feat/tm-pukaar-domain | done |
| 4 | PukaarAgent + store | TM | feat/tm-pukaar-domain | done |
| 5 | FastAPI app + fake mode | TM | feat/tm-pukaar-domain | done |
| 6 | Frontend: caller phone + control room | TM | feat/tm-pukaar-domain | done |
| 7 | Noise drill (script + results card) | TM | feat/tm-pukaar-domain | done |
| 8 | Broadcast alerts (7 languages) | TM | feat/tm-pukaar-domain | done |
| 9 | see plan (Pukaar only) | | | todo |

## Log
- Sun 8 Nov 11:30: docs, design, plan and bootstrap (CL).
- Sun 8 Nov 12:00: TM claims Tasks 1–3 (branch feat/tm-pukaar-domain).
- Sun 8 Nov: TM done Tasks 1–3 (41 tests); claims Tasks 4–5.
- Sun 8 Nov: TM done Tasks 4–5 (51 tests). `FAKE=1 bash run_backend.sh` runs a scripted Tanglish call with no keys.
- Sun 8 Nov: TM done Task 6. Checked in a browser in fake mode (desktop + 390 px). Map tiles moved from CARTO (now needs an API key) to OSM with a dark CSS filter. sw.js now loads pages network-first (the old cache-first `/` served stale builds). package-lock synced (was missing leaflet and 2 fonts, so `npm ci` failed).
- Sun 8 Nov: TM extras: pre-rendered fillers + rain noise (slider now works); missed-call → callback jugaad; flood-night surge (synthetic text callers through the real triage, recorded once and replayed with no tokens; 24-caller demo recording committed); canonical gazetteer names; drill (`scripts/run_drill.py`, `--rescore` uses the LLM only). Groq free tier = 8k tokens/min: prompts trimmed to 6 turns. README + `docs/06-demo-and-post.md` written. Task 8 (broadcast) done later the same day.
- Tue 10 Nov 18:40: CL final review on `feat/cl-pukaar-final` (not merged): 15 findings, 14 fixed (relay/dispatch translations can no longer add times, numbers or "you are safe"; a merged caller can no longer lower a critical incident; no "high place" advice for fire/landslide/collapse; "soon" promises blocked in ta/te/hi/en; SMS: GEN-01, duplicates, romanised language, gps 422; CAP well-formed and XSD-valid; health pill polls; 2 mobile layout fixes). 96 → 110 tests. **Before the live test: sync voice-core (no Gnani gate in this copy).** Details and live checklist: `docs/review-cl-2026-11-10.md`; screenshots: `docs/screenshots/final/`.
