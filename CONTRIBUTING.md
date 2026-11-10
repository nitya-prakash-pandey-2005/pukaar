# Contributing to Pukaar

Thanks for helping. Pukaar answers people in emergencies, so the bar for changes that touch what a caller hears
is high: every such change needs a test.

## Setup

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20 or newer.

```bash
uv sync --all-packages              # backend + the shared voice-core engine
cd frontend && npm ci && cd ..      # control-room and caller web app
cp .env.example .env                # optional: Gnani and Groq keys for live calls
```

No keys? Run everything on fakes: `FAKE=1 bash run_backend.sh` (PowerShell: `$env:FAKE="1"; ./run_backend.ps1`)
starts a scripted Tanglish caller, a fake LLM and tone audio. `cd frontend && npm run dev:demo` runs the static
demo with no backend at all.

## Before you open a pull request

```bash
uv run python -m pytest -q                        # all tests; keyless, no network
uv run --with ruff ruff check backend scripts     # lint (config in pyproject.toml)
cd frontend && npm run build && npm run build:demo
uv run python scripts/export_openapi.py --check   # if you changed a REST route: re-run without --check
```

CI (`.github/workflows/ci.yml`) runs the tests and both frontend builds on every push and pull request to `main`.

## Rules for changes

- **What a caller hears goes through `guard.guard_reply`.** Never speak LLM text that has not passed the guard:
  only approved guidance ids, no arrival time without a dispatcher's ETA, no "you are safe". New languages need
  their time and reassurance words added to `guard.py`, with tests.
- **Severity stays explainable.** Change points in `domain.score` only with a test, and keep every point visible
  as a driver.
- **Tests never call Gnani or the LLM.** Use `voice_core.testing.FakeLLM`, the fakes in `pukaar.fake_mode`, and
  a `tmp_path` store. Never commit keys, `.env`, databases, `cache/` or recordings.
- **Synthetic data only.** Demo callers, surge and drill cases must not contain real names or phone numbers.
- **`voice-core/` is shared** with the team's other products: keep changes to it generic and backwards compatible.
- Keep changes small and focused; use conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `ci:`).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit and [docs/API.md](docs/API.md) for the
REST and WebSocket protocols.
