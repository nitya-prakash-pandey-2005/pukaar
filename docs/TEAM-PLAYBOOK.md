# Team playbook: Gnani "Great Indian AI Internship Challenge"

Deadline: **Tue 10 Nov 2026, 11:59 PM IST** (we aim to submit by **8:00 PM**). One entry per team.
Three repos, one shared engine. We build and promote all three, and **submit one** (Dadi, unless something else ends up clearly better).

| Repo | What it is | Owner |
|---|---|---|
| `dadi-vs-scammers` | AI grandmother who answers scam calls, wastes the scammer's time, extracts mule accounts | Nitya + Claude (on Nitya's laptop) |
| `apni-awaaz` | Voice banking: speak in your own cloned voice after losing it | Claude, after Dadi |
| `pukaar` | AI disaster helpline with triage and a live rescue map | **Teammate** (with an AI assistant, from `pukaar/docs/`) |

Read first: `docs/00-challenge-brief.md` (rules), `docs/01-gnani-api-reference.md` (API facts), `docs/03-design.md` (architecture).

---

## 1. Who does what

**Nitya (primary registrant; on a train 8–9 Nov with patchy network; in Chennai from the morning of 10 Nov)**
- Registers the team (Nitya's email = primary, teammate's email in "Team Member's Email ID").
- Creates the Gnani API key(s) and shares them privately.
- Creates the 3 private GitHub repos and adds the teammate as a collaborator.
- Product owner for Dadi; plays the "scammer" in the Dadi demo; writes and publishes posts; makes the final submission.

**Teammate (stable internet, NVIDIA laptop with less than 8 GB VRAM or 16 GB RAM, so it cannot run Evon locally)**
- **WP-1: host Evon** and evaluate it (see `docs/EVON-HOSTING.md`). This is the top priority today.
- **WP-2: test all three projects** with real voice and network (section 6).
- **WP-3: build Pukaar** from `pukaar/docs/` with your AI assistant.
- **WP-4: demo support:** screen recordings, editing, resharing and commenting from your own account.

**Claude (runs on Nitya's laptop)**
- Shared engine `voice-core` (first), then Dadi end to end, then Apni Awaaz.
- Writes specs, test scripts and the interview-prep and submission documents.

## 2. Timeline (IST)

| When | Nitya | Teammate | Claude |
|---|---|---|---|
| **Sun 8 Nov, by 11:00** | Register team, create keys, create repos, add teammate, share keys | Install tools (section 3), request Hugging Face access to Evon | Push `dadi-vs-scammers` skeleton and docs |
| Sun afternoon | (train) | **Evon endpoint live** (WP-1) | `voice-core` done and pushed (about 14:00), Pukaar spec written |
| Sun evening | test Dadi when the signal is good | Evon evaluation report; start Pukaar | Dadi live call working (P0) |
| **Mon 9 Nov** | review, record the scammer side of the demo | test Dadi (WP-2); build Pukaar; record and edit the Dadi demo video | Dadi polish (P1), Arena, then Apni Awaaz |
| **Mon 9 Nov, evening** | **Publish the Dadi post on LinkedIn + X** (or the teammate publishes if Nitya has no signal) | reshare and comment from your own account | write the submission text |
| Tue 10 Nov, morning | in Chennai: final checks | Pukaar demo video | Awaaz polish |
| **Tue 10 Nov, by 20:00** | **Submit** (one entry) | double-check links | final README / interview pack |

Engagement only counts until the cutoff, so **the earlier the Dadi post is live, the better**. No engagement swaps, bots or paid promotion: the rules disqualify those. Ask real friends and family to genuinely share.

## 3. One-time setup (about 10 minutes)

Prerequisites: Git, **uv** (`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` on Windows or `curl -LsSf https://astral.sh/uv/install.sh | sh`), **Node 22+**.

```bash
mkdir gnani-challenge && cd gnani-challenge     # all 3 repos must sit side by side
git clone https://github.com/<NITYA_GITHUB>/dadi-vs-scammers.git
git clone https://github.com/<NITYA_GITHUB>/apni-awaaz.git
git clone https://github.com/<NITYA_GITHUB>/pukaar.git

cd dadi-vs-scammers
uv sync --all-packages            # installs Python 3.12 and all packages into .venv
cp .env.example .env              # then fill in the keys (section 4)
uv run pytest -q                  # all tests should pass
cd frontend && npm install && cd ..
```
Repeat `uv sync --all-packages`, `cp .env.example .env` and `npm install` in `pukaar/` and `apni-awaaz/` once they have code.

## 4. Keys and credits

| Key | Who gets it | Where it goes |
|---|---|---|
| `GNANI_API_KEY` | Created by Nitya at app.gnani.ai/voice (one per person if the dashboard allows; all keys draw from the same 5,000 team credits) | `.env` in each repo |
| `GROQ_API_KEY` | Each person makes their **own** free key at console.groq.com/keys (double the free limits) | `.env` |
| `HF_TOKEN` | Teammate's own Hugging Face read token | only on the GPU machine |
| `EVON_BASE_URL`, `EVON_API_KEY`, `EVON_MODEL` | Teammate, once Evon is hosted | `.env` (share privately) |

Rules:
- **Never commit `.env`** (it is git-ignored). Share keys only by private DM. If a key leaks, delete it in the dashboard and make a new one.
- **The 5,000 Gnani credits are shared and do not double for a team.** Our code caches every generated voice clip in `cache/` so we never pay twice for the same audio. Test with short sentences. Check usage on the dashboard every evening; if more than 60% is used by Monday night, stop non-essential testing.

## 5. Git workflow

- `main` always works. Never force-push `main`.
- Branches: `feat/<who>-<topic>`, e.g. `feat/tm-evon`, `feat/tm-pukaar-map`, `feat/np-copy`. Small pull requests, merged into `main` with "Squash and merge".
- Commit messages: `feat: …`, `fix: …`, `docs: …`, `test: …`.
- **No AI co-author lines.** Commits must NOT contain `Co-Authored-By: Claude …`, "Generated with Claude Code" or similar (Nitya's rule for these repos). Turn that option off in your AI assistant.
- **Shared engine rule:** `voice-core/` is edited **only in `dadi-vs-scammers`**. To use the latest engine in the other repos, run `bash dadi-vs-scammers/scripts/sync-core.sh` and commit the result in `pukaar` / `apni-awaaz`. If Pukaar needs an engine change, make it in `dadi-vs-scammers/voice-core` on a branch, open a pull request, then sync.
- Before every push: `uv run pytest -q` passes and `npm run build` passes.

## 6. WP-2: test protocol (all three projects)

Use only synthetic data: no real phone numbers, account numbers, Aadhaar, PAN or recorded calls.

For every test, write one line in `docs/test-log.md`: date and time, build (git short hash), scenario, result, latency numbers, notes.

**Dadi checklist**
1. `uv run python voice-core/scripts/smoke_gnani.py --llm` prints PASS for each check. Note the latencies and the **concurrency** result.
2. Run the backend and frontend (see the repo README). Use **earphones** while playing the scammer.
3. Scenarios: digital arrest ("Main CBI se bol raha hoon…"), KYC block, electricity bill, lottery/KBC, job/task. Each call should run 3 minutes or more.
4. Check: a filler plays within about 0.5 s; the first real reply comes within about 1.5 s; Dadi stops talking when you interrupt; the UPI ID and phone number you speak appear in the intel card; the complaint report opens.
5. Repeat with the noise slider at 10, 5 and 0 dB. Note which words Prisma gets wrong.
6. Speak Tamil, then Bengali: Paati and Thakuma should answer in that language.
7. Pull the network cable or turn Wi-Fi off for 5 s mid-call: the status shows "reconnecting", then the call continues.

**Pukaar and Awaaz:** checklists will live in each repo's `docs/`.

Report bugs as GitHub issues: title, steps, what you expected, what happened, log excerpt.

## 7. Help
- Gnani Discord: discord.gg/aECcvtABpq. Useful question to ask there: "Can we use another LLM alongside Prisma and Timbre, given that Evon isn't on the API platform?" (Gnani's own Pipecat example pairs their speech with Groq, so this is very likely fine.)
- Gnani docs: docs.gnani.ai (index: docs.gnani.ai/llms.txt).
