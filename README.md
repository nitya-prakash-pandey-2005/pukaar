# Pukaar (पुकार): AI disaster helpline

**An AI disaster helpline that answers every call during floods, cyclones and landslides in the caller's own language, keeps them calm, gives only approved safety instructions, triages severity with explainable rules, merges duplicate reports and puts every caller on a live rescue map. A human confirms every dispatch.**

Built on Gnani AI's voice stack: **Prisma v3.0** (speech-to-text for noisy 8 kHz, code-mixed phone audio) and **Timbre v3.0** (text-to-speech). Part of our entry to Gnani AI's *Great Indian AI Internship Challenge* (#GnaniAI #GreatIndianAIInternshipChallenge). All calls in demos are simulated with synthetic data.

## Why
During the Chennai floods (2015, Cyclone Michaung 2023), the Kerala floods (2018) and the Wayanad landslides (2024), helplines were overwhelmed exactly when calls mattered most. Pukaar is an **overflow layer**: no call goes unanswered, and a small control-room team sees every caller.

Prior art exists (Bengaluru's multilingual "Namma 112" assistant, Corti, Prepared, Aurelian). Our difference: built for the **disaster surge**, **grounded advice only**, **explainable severity**, **duplicate merging**, **callbacks in the caller's language**, and a **measured noise drill**.

## What it does
- **Live voice calls** in Tamil, Tanglish, Hindi, Telugu and English (Prisma `indic-auto`, codemix). Pukaar reassures, asks one question at a time (location → people → injuries → water → vulnerable people), and may add one approved instruction.
- **Triage you can explain:** the LLM only extracts facts; a fixed rule table scores severity (critical ≥ 70), shown as driver bars. "We don't let an AI decide who gets rescued first."
- **Guardrails:** advice only by ID from `backend/data/guidance_kb.json`; a guard replaces any invented advice or unconfirmed arrival time ("10 minutes", "jaldi pahunch") with a safe line.
- **Rescue map + queue:** phone location (simulated) plus a Chennai gazetteer with Tamil aliases; reports within 300 m merge into one incident ("3 callers").
- **Human dispatch + callback:** the dispatcher confirms team and ETA; the caller hears it in their language, live or as a "missed callback".
- **Jugaads:** *missed-call mode* (no balance? give a missed call, Pukaar calls back); *flood-night surge* (24 synthetic callers replayed from a recording, so the demo costs no tokens or credits); *pre-rendered fillers* so replies never start with silence.
- **Noise drill:** synthetic calls spoken by Timbre, band-limited to 8 kHz, buried in rain at 0–20 dB, transcribed by Prisma, then triaged. Results: [`docs/drill-results.md`](docs/drill-results.md).

## Architecture
```
Caller (browser mic, 8 kHz PCM) ──WS /ws/call──► FastAPI
  VoiceAgentSession (voice-core) ──► Prisma v3.0 realtime (indic-auto, codemix, keyterms)
  PukaarAgent
    ├─ on_user_turn: LLM fact extraction → merge → gazetteer/GPS locate → severity rules → dedup → incident
    ├─ reply: next missing slot + ≤1 approved instruction → LLM → guard → sentences
    └─ voice: Timbre v3.0 "Chetana" (fillers pre-rendered, cached)
Control room ──WS /ws/control──► incidents, KPIs, live calls; dispatch → REST → callback speech
```
Shared engine `voice-core/` is synced from `dadi-vs-scammers` (contract: `voice-core/README.md`).

## Run
```bash
bash ../dadi-vs-scammers/scripts/sync-core.sh   # latest shared engine (optional)
uv sync --all-packages
cp .env.example .env                              # GNANI_API_KEY, GROQ_API_KEY (GROQ_MODEL=qwen/qwen3.8-27b)
uv run pytest -q
cd frontend && npm ci && npm run build && cd ..
bash run_backend.sh                               # http://127.0.0.1:8766 (serves the built UI)
FAKE=1 bash run_backend.sh                        # no keys: scripted Tanglish caller
uv run python scripts/run_drill.py --n 6          # noise drill (spends Gnani credits; TTS cached)
```
Frontend dev server: `cd frontend && npm run dev` (http://localhost:5192, proxies to 8766).

## Notes from testing (Nov 2026)
- Prisma streaming accepts exactly one `language_code` (or `indic-auto`); locale lists close the socket with 1008. Keyterms must be ASCII-escaped JSON.
- Groq's free tier allows 8k tokens/min, so the surge replays a recording by default (`{"fresh": true}` regenerates).
- Details: [`docs/test-log.md`](docs/test-log.md). Demo and post kit: [`docs/06-demo-and-post.md`](docs/06-demo-and-post.md).
