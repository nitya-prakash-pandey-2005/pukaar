# Pukaar (पुकार): AI disaster helpline

**An AI disaster helpline that answers every call during floods, cyclones and landslides in the caller's own language, keeps them calm, gives only approved safety instructions, triages severity with explainable rules, merges duplicate reports and puts every caller on a live rescue map. A human confirms every dispatch.**

Built on Gnani AI's sovereign voice stack: **Prisma v3.0** (speech-to-text, trained on noisy 8 kHz calls), **Timbre v3.0** (text-to-speech) and **Evon v3.3** (LLM).
Part of our entry to Gnani AI's *Great Indian AI Internship Challenge* (#GnaniAI #GreatIndianAIInternshipChallenge).

> **New here? Read `docs/START-HERE.md` first.** Status: under active development (8–10 Nov 2026). Read `docs/02-design.md`, then `docs/03-build-plan.md`. Team rules: `docs/TEAM-PLAYBOOK.md`. Task board: `docs/STATUS.md`.

## Quick start
```bash
bash ../dadi-vs-scammers/scripts/sync-core.sh   # get the latest shared engine
uv sync --all-packages
cp .env.example .env                              # add GNANI_API_KEY and GROQ_API_KEY
uv run pytest -q
cd frontend && npm install && npm run dev         # http://localhost:5192
```
All calls in demos are simulated with synthetic data.
