# Static demo on Vercel

The live demo link is the real Pukaar frontend in **demo mode**. It has no backend, no API keys and spends no Gnani or Groq credits.
- **What it shows:** a real run recorded on Gnani's live servers on 10 Nov 2026, with synthetic callers.
- **The banner:** every page says this plainly and links to this repo.
- **Why not host the backend:** Vercel cannot run the Python backend (WebSockets, secret keys). A public live backend would also burn the team's shared Gnani key.

## Deploy (about 2 minutes)

1. In Vercel, choose **Add New… → Project**, then import the `pukaar` GitHub repository.
2. **Keep the Root Directory as the repository root.** The build needs `voice-core/web/` next to `frontend/`.
3. Change nothing else. [`vercel.json`](../vercel.json) already sets:
   - framework: none
   - install: `cd frontend && npm install`
   - build: `cd frontend && npm run build:demo`
   - output: `frontend/dist`
4. **Do not add any environment variables.** No keys go to Vercel.
5. Click **Deploy**, open the URL, and check:
   - the cyan "Interactive demo" banner is there;
   - the "Recorded run · 10 Nov" pill shows in the top bar;
   - "Play a recorded call" plays a Tamil call.
6. Replace the `*[live demo link]*` placeholders in `README.md` and `PITCH.md` with the URL (and `*[video link]*` with the video URL), then regenerate the one-page PDF: `uv run --no-project --with markdown --with pypdf python scripts/make_pitch_pdf.py` (it shrinks the font until `PITCH.pdf` is one page).

To check locally before deploying:

```bash
cd frontend
npm run build:demo
python -m http.server 4173 -d dist     # or any static server; open http://127.0.0.1:4173
```

`npm run dev:demo` runs the same demo on Vite's dev server (http://localhost:5192), also with no backend.

## What the demo does

| In the app | In demo mode |
|---|---|
| Every GET (`/api/incidents`, `/api/calls/…`, `/api/drill`, …) | Served from JSON snapshots in `frontend/demo/api/` |
| Control room (`/ws/control`) | Starts from the recorded end state (10 Nov: 16 incidents, 25 calls) |
| Simulate surge | Replays the recorded surge: the synthetic text callers arrive at their recorded pace (about 20 s) |
| Call Pukaar (`/ws/call`) | "Play a recorded call" replays live call `9c104531d25e` turn by turn, in real time. Includes the caller's audio, Pukaar's Timbre greeting, the Prisma transcripts with their timings, and severity rising (low → high → critical 90). No microphone is used. Pukaar's replies were streamed during the run and not saved, so they show as captions only. |
| Broadcast alert | The recorded Tamil, Hindi, Telugu and English alert, with its real Timbre MP3s |
| CAP 1.2 export | The CAP XML exported during the run |
| Dispatch, resolve, missed call | Work in the browser: the incident, map and KPIs update |
| Message the callers; SMS with new text; broadcast in Malayalam, Kannada or Bengali | Say plainly that this needs the live server. A new SMS shows the recorded reply to a Tamil SMS, labelled as a recording. |

How the demo build works:
- **The switch:** `import.meta.env.VITE_DEMO === "1"`, set by `frontend/.env.demo` when you run `vite build --mode demo`.
- **Interception:** `frontend/src/demo/demo.js` swaps `fetch` and `WebSocket` for `/api` and `/ws` URLs only. The app's own components are unchanged.
- **Microphone:** `useCall` skips the microphone.
- **Service worker:** none is registered, and any old one is removed.
- **Recorded files:** `vite.config.js` copies `frontend/demo/` into `dist/demo/` only in demo mode. The normal `npm run build` neither includes nor changes any of this.

## Refresh the recorded data after a new live run

```bash
# after a live run (bash run_backend.sh with keys), from the repo root. All three flags are optional:
#   --caller-wav  the synthetic caller audio that was fed to the mic
#   --cap         a CAP file downloaded during the run
#   --call        which voice call to replay (default: the first one)
uv run python scripts/snapshot_demo.py --caller-wav path/to/caller.wav --cap path/to/pukaar-alert-cap.xml
```

What the script does:
- **Safe by construction:** it runs the real FastAPI app in-process on `cache/pukaar.db` and `cache/tts/`. Every key is blanked, the LLM is a dummy that raises if called, and voice sessions are disabled, so it cannot reach Gnani or Groq.
- **What it writes:** everything under `frontend/demo/`:
  - the GET snapshots;
  - the decision-support GETs (`teams`, `plan`, `hotspots`, `sitrep`, `incidents/{id}/recommend`), written by `scripts/snapshot_decision.py` from the recorded incidents with the same pure functions as the server (it runs at the end of `snapshot_demo.py`, or alone: `uv run python scripts/snapshot_decision.py`). In the browser, a team dispatched during the demo shows as busy and leaves the plan (`src/demo/demo.js`);
  - `control.json` (the end-state snapshot and the surge timeline);
  - `call.json` (the call timeline; the severity stages are recomputed with the same rule table from the facts said so far);
  - `broadcast.json` (texts from the CAP file, audio from the Timbre cache);
  - `sms.json`;
  - the audio files.
- **Without the optional flags,** the existing `caller.wav` and `cap.xml` are kept.

Then run `cd frontend && npm run build:demo`, check the result, and commit `frontend/demo/`. Vercel redeploys on push.

**Never commit** `cache/pukaar.db`, `.env` or real people's audio. Everything in `frontend/demo/` must be synthetic.
