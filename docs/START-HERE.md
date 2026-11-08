# START HERE (teammate + your AI assistant)

**Give this file to your AI assistant first.** It explains the whole situation in two minutes.

## The contest
Gnani AI's "Great Indian AI Internship Challenge". Build a working app on Gnani's models (Prisma STT, Timbre TTS, Evon LLM), post a public demo video on LinkedIn and X with **#GnaniAI #GreatIndianAIInternshipChallenge**, tagging Gnani AI, and submit **one** entry. **Deadline: Tue 10 Nov 2026, 11:59 PM IST (we submit by 8 PM).** The shortlist is decided by real engagement on the post, so **post early**. Full rules: `docs/00-challenge-brief.md`.

## The team
- Nitya (primary registrant; on a train until 10 Nov morning, patchy network).
- You (teammate; stable internet).
- Claude (an AI coding agent running on Nitya's laptop; builds while that laptop is online).

## The three repos (clone all three side by side in one folder)
| Repo | What | Built by | Status (Sun 8 Nov, 11:00) |
|---|---|---|---|
| `dadi-vs-scammers` | AI grandmother who answers scam calls, wastes the scammer's time and extracts mule accounts. **This is our submission.** | Claude | Engine and backend done (49 tests). Frontend in progress. **Needs a live test with real keys** |
| `pukaar` | AI disaster helpline: triage plus a live rescue map | **You** | Design and plan ready; engine synced; code not started |
| `apni-awaaz` | Speak again in your own cloned voice | **You (after Pukaar)** | Design and plan ready; engine synced; code not started |

Shared engine `voice-core/` (Gnani clients, LLM adapter, realtime voice session): its contract is `voice-core/README.md`. **Edit it only in `dadi-vs-scammers`**, then run `bash dadi-vs-scammers/scripts/sync-core.sh`.

## Your priorities, in order
1. **Setup** (`docs/TEAM-PLAYBOOK.md` §3): `uv sync --all-packages`, `.env` with the keys Nitya sends you, `uv run pytest -q`.
2. **Smoke test Gnani** (in `dadi-vs-scammers`): `uv run python voice-core/scripts/smoke_gnani.py --llm --voices`. Paste the output into `docs/test-log.md` and push. It tells us whether Gnani allows two requests at once (`STT_MODE=stream` or `turn`).
3. **Host Evon** (`docs/EVON-HOSTING.md`): request Hugging Face access now, then get an endpoint running, then run `voice-core/scripts/eval_llm.py`.
4. **Build Pukaar** with your assistant from `pukaar/docs/02-design.md` and `03-build-plan.md` (TDD, small commits). Claim tasks in `pukaar/docs/STATUS.md`.
5. **Live-test Dadi** once the frontend lands (`dadi-vs-scammers/docs/TEAM-PLAYBOOK.md` §6) and **record the Dadi demo video** with good internet (Nitya is on a train).
6. Apni Awaaz, if time remains.

## Hard rules
- **No AI co-author lines in commits** (no `Co-Authored-By: Claude`, no "Generated with …"). Turn this off in your assistant.
- Never commit `.env` or keys. Share keys only in private DMs.
- Synthetic data only: no real phone numbers, account numbers, Aadhaar, PAN or recorded calls in code or demos.
- The 5,000 Gnani credits are shared by the team: keep tests short, and audio is cached in `cache/`.
- Work on branches `feat/tm-<topic>` and merge small pull requests. `main` must always pass `uv run pytest -q` and `npm run build`.

## How to run Dadi
```bash
cd dadi-vs-scammers
uv sync --all-packages && cp .env.example .env   # add keys
bash run_backend.sh                               # or: FAKE=1 bash run_backend.sh (no keys, scripted scammer)
cd frontend && npm install && npm run dev         # http://localhost:5191  (use earphones when you play the scammer)
```
