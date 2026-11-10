# Pukaar API reference

The backend is one FastAPI app (`backend/pukaar/app.py`, `create_app()`), served by `bash run_backend.sh` on port
8766. It has three surfaces:

| Surface | Path | Who uses it |
|---|---|---|
| REST | `/api/...` | the control-room web app, the SMS gateway, scripts |
| Caller WebSocket | `/ws/call` | the caller's phone page: PCM16 audio both ways plus JSON events |
| Control-room WebSocket | `/ws/control` | every open control-room screen: a snapshot, then live events |

The machine-readable schema of the REST routes is [`docs/api/openapi.json`](api/openapi.json). It is generated
in-process, in fake mode, with no keys and no network:

```bash
uv run python scripts/export_openapi.py          # rewrite docs/api/openapi.json
uv run python scripts/export_openapi.py --check  # exit 1 if it is stale
```

A running backend also serves the interactive docs at `http://localhost:8766/docs`. WebSockets are not part of
OpenAPI, so this page documents them. This page covers the routes on `main` as of 10 Nov 2026; if a route is
added later, re-run the export and add it here.

Errors use FastAPI's shape: `{"detail": "incident not found"}` with 404, `{"detail": "message is empty"}` with
400, `{"detail": "a surge is already running"}` with 409, and a 422 with field errors when a body does not match
its model (for example `gps` that is not a `[lat, lon]` pair).

## Data shapes

**Incident** (`domain.Incident`): one pin on the map. Several calls and texts about the same place and hazard
merge into one incident (see `docs/ARCHITECTURE.md`, "Incident store and dedup").

```json
{
  "id": "3f2a9c1b7d4e",
  "call_ids": ["a1b2c3d4e5f6", "0f9e8d7c6b5a"],
  "facts": {
    "locality": "Velachery", "landmark": "bus depot", "lat": null, "lon": null,
    "hazard": "flood", "people_count": 4, "trapped": null, "on_roof": true, "water_level": "chest",
    "vulnerable": ["elderly"], "injuries": [], "medical_needs": ["insulin"], "needs": [],
    "caller_language": "ta-IN"
  },
  "lat": 12.9791, "lon": 80.2209, "loc_source": "gps", "loc_confidence": 0.7,
  "severity": {
    "score": 84, "level": "critical",
    "drivers": [
      {"label": "Hazard: flood", "contribution": 20}, {"label": "Water: chest", "contribution": 30},
      {"label": "On roof", "contribution": 10}, {"label": "Vulnerable: elderly", "contribution": 8},
      {"label": "Medical: insulin", "contribution": 10}, {"label": "People: 4", "contribution": 6}
    ]
  },
  "status": "new",
  "dispatch": null,
  "guidance_given": ["FLD-03"],
  "channel": "voice",
  "created_at": 1762785000.12, "updated_at": 1762785041.80
}
```

- `facts` enums: `hazard` in `flood, cyclone, landslide, fire, building_collapse, medical, other`; `water_level` in
  `none, ankle, knee, waist, chest, neck`; `vulnerable` from `infant, child, elderly, pregnant, disabled, sick`;
  `injuries` from `bleeding, fracture, unconscious, burn, other`; `medical_needs` from
  `oxygen, labour, dialysis, insulin, medication`; `needs` from `boat, ambulance, food, water, medicine, evacuation`.
  Unknown values from the LLM are dropped, never raised.
- `loc_source`: `gps`, `landmark` (gazetteer centre of the named place), `both`, or `""` (not located yet).
- `severity.level`: `critical` (score 70+), `high` (45+), `medium` (25+), `low`. `drivers` lists every point
  that made the score, so a dispatcher can see why.
- `status`: `new`, `dispatched`, `resolved`. `dispatch` is `{"team", "note", "eta"}` once dispatched.
- `channel`: `voice`, `missed_call` or `text` (SMS and the synthetic surge).

**KPIs** (`Store.kpis()`):

```json
{"calls": 27, "avg_answer_s": 1.42, "critical_open": 3, "people_affected": 61}
```

`avg_answer_s` is the mean LLM time to the first reply sentence (null before the first reply);
`people_affected` counts `people_count` (or 1) over open incidents.

## REST routes

### Status and reference data

| Method and path | Returns |
|---|---|
| `GET /api/health` | `{"gnani_key": bool, "llm_key": bool, "llm_provider", "intel_llm_provider", "stt_mode", "fake": bool, "fillers_ready": bool}`. Says whether keys are set, never their values. |
| `GET /api/places` | The Chennai gazetteer: `[{"name", "aliases", "lat", "lon"}]`. Aliases include Tamil-script names. |
| `GET /api/guidance` | The approved safety-guidance knowledge base: `[{"id": "FLD-03", "hazards", "when", "text_en"}]`. The caller agent may only speak these, by id. |
| `GET /api/kpis` | The KPI object above. |
| `GET /api/drill` | The noise-drill results written by `scripts/run_drill.py` (`{"rows": [...], "summary": {...}}`), or `{"rows": [], "summary": null}`. |

### Incidents

| Method and path | Body | Returns |
|---|---|---|
| `GET /api/incidents?status=new` | none; `status` optional | Incidents, most severe first (ties: oldest first). |
| `GET /api/incidents/{id}` | none | One incident, or 404. |
| `POST /api/incidents/{id}/dispatch` | `{"team": "NDRF boat 2", "note": "", "eta": "20 minutes"}` (`eta` optional) | The dispatched incident. Every live caller of the incident hears the dispatch in their own language; a caller who hung up gets a queued callback. Live callers' later replies may now mention the ETA. |
| `POST /api/incidents/{id}/message` | `{"text": "Move to the terrace and wave a torch"}` | `{"sent": [{"call_id", "lang", "text", "live": bool}]}`. The dispatcher's English is translated per caller (translation only: a translation that adds a time, a number or "you are safe" is replaced by the English). 400 if empty. |
| `POST /api/incidents/{id}/resolve` | none | The resolved incident. Resolved incidents never merge new reports. |

Dispatch, resolve, SMS and missed-call also push `incident` and `kpis` events to every control-room socket.

### More ways in

| Method and path | Body | Returns |
|---|---|---|
| `POST /api/sms` | `{"text": "Saidapet bridge ke paas hum 3 log hain, paani kamar tak", "gps": [13.02, 80.22]}` (`gps` optional) | `{"incident": Incident, "reply": "..."}`. SMS or WhatsApp intake for people who cannot talk: the text goes through the same triage and guard as a call; `reply` is the guarded reply SMS in the texter's language. The same 4+ word text again within 3 hours returns the same incident and reply with no new LLM call. Text is capped at 1000 characters. |
| `POST /api/missed-call` | `{"gps": [12.98, 80.22]}` (optional) | `{"call_id", "incident"}`. The caller spends nothing: a pin appears at once (`channel: "missed_call"`), and the call back reuses `call_id` (see `callback_for` below). |
| `POST /api/surge` | `{"n": 20, "fresh": false}` | `{"started": n, "mode": "replay" | "generate"}`. Flood-night load demo: replays a recorded set of synthetic text callers (no LLM calls), or with `fresh: true` generates new ones through the real triage. `n` is clamped to 1..40. 409 while one runs. Fake mode always replays the committed recording. |

### Callbacks

| Method and path | Returns |
|---|---|
| `GET /api/calls/{call_id}` | The call row with its turns: `{"id", "lang", "started_at", "ended_at", "seconds", "incident_id", "reply_s", "replies", "turns": [{"speaker", "text", "t", "lang", "latency_ms"}]}`, or 404. |
| `GET /api/calls/{call_id}/callbacks` | Queued messages for a caller who hung up: `[{"id", "text", "lang", "created_at"}]`. |
| `GET /api/calls/{call_id}/callbacks/{cb_id}/audio` | That message spoken by Timbre as `audio/wav` (PCM16 mono at the app sample rate, 8 kHz by default; cached on disk). Fake mode returns a tone. |

### Broadcast alerts

| Method and path | Body | Returns |
|---|---|---|
| `POST /api/broadcast` | `{"text_en": "Adyar river is rising. Move to the first floor now.", "langs": ["ta-IN", "hi-IN", "en-IN"]}` (`langs` defaults to all 7: `ta-IN, hi-IN, te-IN, en-IN, ml-IN, kn-IN, bn-IN`) | `[{"lang", "language", "text", "audio_url"}]`. One LLM call translates into every language; known place names are masked as `{P1}` first so they cannot be mistranslated, then restored in the target script. A language whose translation lost a place token is skipped. 400 if empty. |
| `GET /api/broadcast/audio/{key}` | none | The cached audio (`audio/mpeg`, or `audio/wav` in fake mode). `key` must be 40 hex characters, else 404. |
| `POST /api/broadcast/cap` | `{"text_en": "...", "items": [{"lang": "ta-IN", "text": "..."}], "area": "Chennai"}` | A CAP 1.2 XML file (`application/xml`, `Content-Disposition: attachment; filename=pukaar-alert-cap.xml`) with one `<info>` per language. `status` is `Exercise` until an authority issues the alert. Characters XML 1.0 cannot carry are dropped. |

CAP output, shortened:

```xml
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>pukaar-1762785000-1a2b3c4d</identifier><sender>pukaar@district-eoc.example</sender>
  <sent>2026-11-10T20:30:00+05:30</sent><status>Exercise</status><msgType>Alert</msgType><scope>Public</scope>
  <info>
    <language>ta-IN</language><category>Met</category><event>Flood</event><urgency>Immediate</urgency>
    <severity>Severe</severity><certainty>Likely</certainty><headline>Adyar river is rising...</headline>
    <description>(Tamil text)</description><area><areaDesc>Chennai</areaDesc></area>
  </info>
</alert>
```

## Caller WebSocket: `/ws/call`

One socket per call. Audio is raw **PCM16 little-endian mono at 8 kHz** (the app sample rate; phone quality, which
is what Prisma is trained on) in binary frames, both ways. Everything else is JSON text frames.

**1. Open** with a `start` message. Any other first message closes the socket with code 1008.

```json
{"type": "start", "gps": [12.9791, 80.2209], "noise_snr_db": 10, "callback_for": "a1b2c3d4e5f6"}
```

All fields but `type` are optional. `gps` is `[lat, lon]`. `noise_snr_db` mixes synthetic rain into the caller's
audio at that SNR before speech-to-text (the noise demo). `callback_for` continues an earlier call (a missed call
or a caller who hung up): the new session reuses that call id and its incident, and greets with the callback line.
It is ignored if the call does not exist or is still live.

**2. Server to caller:**

| Message | When |
|---|---|
| `{"type": "session_started", "started_at": 1762785000.1, "call_id": "a1b2c3d4e5f6", "gps": [12.97, 80.22]}` | At once; the greeting audio starts right after, before speech-to-text is even connected. |
| binary frame | Agent speech (greeting, fillers, replies) as PCM16. |
| `{"type": "agent_speaking", "on": true}` / `false` | Speech starts / ends. |
| `{"type": "stop_audio"}` | Barge-in: the caller spoke over the agent; drop buffered audio. |
| `{"type": "turn", "speaker": "caller", "text": "Velachery la irukom...", "t": 6.2, "lang": "ta-IN", "latency_ms": 180.0}` | A caller turn from Prisma. |
| `{"type": "turn", "speaker": "pukaar", "text": "...", "t": 7.9}` | An agent turn. It adds `"fallback": true` when the reply produced no audio and a pre-rendered clip was spoken instead, so the caller never hears dead air. |
| `{"type": "language", "call_id": "...", "language": "ta-IN", "language_name": "Tamil"}` | Once, on the first caller turn in a language Timbre speaks; replies switch to it. |
| `{"type": "incident", "call_id": "...", "incident": {...}}` | After each caller turn: the facts so far, the severity and the pin. |
| `{"type": "status", "stt": "reconnecting" \| "connected" \| "error", "message": "..."}` | Speech-to-text link state (it reconnects with backoff on weak networks). |
| `{"type": "session_ended", "session_seconds": 74.3}` then `{"type": "call_ended", "call_id": "...", "seconds": 74.3}` | On hang-up. |

**3. Caller to server:**

| Message | Effect |
|---|---|
| binary frame | Microphone audio, PCM16 8 kHz. |
| `{"type": "set_noise", "snr_db": 5}` | Change the injected rain level; `null` turns it off. |
| `{"type": "hangup"}` | End the call (closing the socket does the same). |

## Control-room WebSocket: `/ws/control`

Read-only fan-out. On connect the server sends one snapshot:

```json
{"type": "snapshot", "incidents": [{...}], "kpis": {"calls": 27, "avg_answer_s": 1.42, "critical_open": 3, "people_affected": 61}, "live_calls": ["a1b2c3d4e5f6"]}
```

then pushes every event below to every connected screen. Messages the client sends are read and ignored (they keep
the socket alive). A screen whose send fails is dropped from the fan-out set.

| Event | Source |
|---|---|
| `{"type": "call_started", "call_id": "...", "gps": [12.97, 80.22]}` | A caller socket opened. |
| `{"type": "turn", "call_id": "...", "speaker": "caller", "text": "...", ...}` | Every caller and agent turn of every live call (live transcript). |
| `{"type": "language", "call_id": "...", "language": "ta-IN", "language_name": "Tamil"}` | A call's language was detected. |
| `{"type": "incident", "incident": {...}, "call_id": "..."}` | An incident was created or updated by a call, SMS, missed call, dispatch or resolve. Surge events carry `"synthetic": true` instead of a `call_id`. |
| `{"type": "kpis", ...}` | After every incident change and every call end. |
| `{"type": "call_ended", "call_id": "..."}` | A caller socket closed. |
