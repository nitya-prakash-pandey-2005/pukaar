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
| 6 | see plan | | | todo |
| 7 | see plan (Pukaar only) | | | todo |
| 8 | see plan (Pukaar only) | | | todo |
| 9 | see plan (Pukaar only) | | | todo |

## Log
- Sun 8 Nov 11:30: docs, design, plan and bootstrap (CL).
- Sun 8 Nov 12:00: TM claims Tasks 1–3 (branch feat/tm-pukaar-domain).
- Sun 8 Nov: TM done Tasks 1–3 (41 tests); claims Tasks 4–5.
- Sun 8 Nov: TM done Tasks 4–5 (51 tests). `FAKE=1 bash run_backend.sh` runs a scripted Tanglish call with no keys.
