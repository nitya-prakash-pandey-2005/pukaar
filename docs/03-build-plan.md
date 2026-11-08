# Pukaar: implementation plan

> **For agentic workers:** execute task by task with TDD (write the test, see it fail, implement, see it pass, commit). Steps use `- [ ]` checkboxes. Claim tasks in `docs/STATUS.md`.

**Goal:** browser caller ↔ AI disaster helpline on Gnani Prisma + Timbre, with live triage, an explainable severity queue, a rescue map, human-confirmed dispatch with a voice callback, and a drill mode that measures accuracy under noise.
**Architecture:** reuses `voice-core` (synced from `dadi-vs-scammers`; its contract is `voice-core/README.md`): `VoiceAgentSession` + Gnani clients + LLM adapter. Pukaar adds a domain layer (gazetteer, severity, dedup, guidance, triage), `PukaarAgent` (Agent protocol), SQLite, FastAPI and a React + Leaflet control room.
**Tech:** Python 3.12 (uv workspace), FastAPI, SQLite; React 19 + Vite 6 + ui-kit (JSX), Leaflet 1.9.
**Spec:** `docs/02-design.md`.

## Global constraints
- Same as `dadi-vs-scammers/docs/04-build-plan.md` (Gnani endpoints, 8 kHz PCM16, 1024-byte STT frames, `.env` only, no AI co-author lines in commits).
- STT for calls: `model prisma-v3.0`, `format codemix`, `language_code "ta-IN,hi-IN,en-IN,te-IN"`, keyterms from `pukaar.domain.KEYTERMS`.
- TTS voice `Chetana`, model `timbre-v3.0`, speed 0.95. Callback and broadcast audio use the same voice.
- Disclaimer text on every call and drill screen: **"Simulated emergency call: synthetic data"**.
- The AI never dispatches and never states an arrival time unless a dispatcher entered one.
- Map centre: Chennai (13.0827, 80.2707), zoom 11. Tiles: `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png` with attribution "© OpenStreetMap contributors © CARTO".
- Port: backend **8766**, frontend dev **5192**.

## Review focus (failure modes no happy-path test catches)
1. **Caller gives a landmark but no locality** ("near Velachery bus depot"): `locate()` must match the gazetteer by fuzzy matching on the landmark text too (test in Task 2).
2. **Second caller reports the same family** with slightly different words: it must merge, not create a duplicate pin (test in Task 2).
3. **LLM returns invalid triage JSON** mid-call: keep the previous facts, keep talking, never crash (test in Task 3).
4. **The model invents advice or an arrival time:** an output with an unknown `[[ID]]` or an arrival time ("10 minutes", "jaldi pahunch") without a dispatcher ETA is replaced by a safe fallback line (test in Task 3).
5. **Dispatch after the caller hung up:** the callback is queued and playable from the caller phone's "missed callback" banner (test in Task 5).

---

### Task 0: Bootstrap (if not already pushed)
- Root `pyproject.toml` workspace like Dadi's (members `voice-core`, `backend`; project name `pukaar`; backend package `pukaar`).
- Run `bash ../dadi-vs-scammers/scripts/sync-core.sh`, then `uv sync --all-packages`.
- Frontend: copy `dadi-vs-scammers/frontend` minus `src/pages` (keep the ui-kit parts), change the ports and proxy to 8766, `npm i leaflet@1.9.4`.
- Commit `chore: bootstrap pukaar`.

### Task 1: Data: gazetteer + guidance KB
**Files:** `scripts/build_gazetteer.py`, `backend/data/gazetteer_chennai.json`, `backend/data/guidance_kb.json`, `backend/pukaar/data.py`, test `backend/tests/test_data.py`
**Produces:** `load_gazetteer() -> list[Place]` (`Place(name: str, aliases: list[str], lat: float, lon: float)`; aliases include the Tamil-script name and common spellings); `load_guidance() -> list[Guidance]` (`Guidance(id, hazards: list[str], when: list[str], text_en: str)`).
- `build_gazetteer.py` queries `https://nominatim.openstreetmap.org/search?format=json&q=<name>, Chennai, Tamil Nadu` for: Velachery, Tambaram, Mudichur, Pallikaranai, Adyar, Saidapet, Kotturpuram, Ashok Nagar, KK Nagar, Ramapuram, Manapakkam, Perungudi, Thoraipakkam, Madipakkam, Medavakkam, Chromepet, Pallavaram, Porur, Valasaravakkam, Virugambakkam, Ekkattuthangal, Jafferkhanpet, T Nagar, Mylapore, Royapuram, Vyasarpadi, Kolathur, Perambur, Ambattur, Avadi, Korattur, Anna Nagar, Arumbakkam, Koyambedu, Guindy, Nanganallur, Keelkattalai, Selaiyur, Varadharajapuram, Semmencherry, Sholinganallur, Kodambakkam. Use 1 request/second and `User-Agent: pukaar-hackathon-demo`. Add Tamil aliases by hand (e.g. Velachery → "வேளச்சேரி").
- Tests: ≥ 35 places, all within lat 12.75–13.35 and lon 79.95–80.35; guidance ids unique; ≥ 3 entries with `"flood"`; every id matches `^[A-Z]{3}-\d{2}$`.

### Task 2: Domain: severity, locate, dedup, slots
**Files:** `backend/pukaar/domain.py`, test `backend/tests/test_domain.py`
**Produces:**
- `Facts` (pydantic; fields from design §7, all optional, lists default empty), `merge_facts(old: Facts, new: Facts) -> Facts` (new non-null scalars win; lists union; `people_count` = max)
- `Severity(score: int, level: str, drivers: list[dict])` (`drivers` = `[{"label": str, "contribution": int}]`), `score(f: Facts) -> Severity` (the rule table in design §7)
- `locate(f: Facts, places, gps: tuple[float,float] | None) -> tuple[float, float, str, float] | None` → (lat, lon, source "gps"|"landmark"|"both", confidence). Matches `locality` or `landmark` against names and aliases with `difflib` ratio ≥ 0.75 (case-insensitive, also substring); GPS wins for coordinates, the text match raises confidence.
- `haversine_m(a, b) -> float`; `should_merge(a: Incident, b_facts: Facts, b_latlon, now) -> bool` (design §7 dedup rule)
- `next_slot(f: Facts) -> str | None` returning one of `"location","people","injuries","water_level","vulnerable"` or None
- `KEYTERMS: list[str]` (≤ 40: flood, water, roof, boat, rescue, ambulance, current, landslide, Velachery…)
**Tests (exact values):**
```python
def test_score_critical_example():
    f = Facts(hazard="flood", water_level="chest", on_roof=True, vulnerable=["elderly","infant"], medical_needs=["insulin"], people_count=4)
    s = score(f)
    assert s.score == 20+30+10+20+10+6 and s.level == "critical"   # 96
def test_score_caps_and_low():
    assert score(Facts(hazard="other")).level == "low"
    assert score(Facts(hazard="building_collapse", water_level="neck", trapped=True, on_roof=True, vulnerable=["infant","pregnant","elderly"], medical_needs=["oxygen","labour"], injuries=["unconscious"], people_count=20)).score == 100
def test_locate_by_landmark_alias(places):
    lat, lon, src, conf = locate(Facts(landmark="near வேளச்சேரி bus depot"), places, None)
    assert src == "landmark" and abs(lat-12.98) < 0.05
def test_dedup_merges_same_roof(): ...   # two facts 120 m apart, same hazard, 40 min apart → True; 900 m → False
def test_next_slot_order():
    assert next_slot(Facts()) == "location"
    assert next_slot(Facts(locality="Velachery")) == "people"
```

### Task 3: Triage extraction + reply guardrails
**Files:** `backend/pukaar/triage.py`, `backend/pukaar/guard.py`, test `backend/tests/test_triage.py`
**Produces:**
- `async extract_facts(llm, history: list[Turn], previous: Facts) -> Facts`: JSON-mode prompt listing the allowed enum values; invalid values dropped; on any failure returns `previous` (never raises).
- `build_reply_messages(f: Facts, slot: str | None, guidance: list[Guidance], lang: str, dispatcher_eta: str | None, history) -> list[dict]`: system prompt: "You are Pukaar, a calm disaster helpline. Reply in the caller's language and script (code-mixing is fine), 1–2 short sentences. First reassure in 3–6 words. Then ask exactly ONE question for slot <slot>. You may add at most one instruction from the list, ending with its id in double brackets like [[FLD-03]]. Never invent advice. Never promise an arrival time unless the ETA is given: <eta or 'none'>."
- `pick_guidance(f: Facts, kb, already: set[str]) -> list[Guidance]` (≤ 2, filtered by hazard and water level)
- `guard_reply(text: str, allowed_ids: set[str], eta: str | None) -> tuple[str, list[str]]`: returns (speakable text with `[[ID]]` removed, used ids). If an id is not allowed, **or** when `eta is None` the text matches the time-promise regex `(\d+\s*(min|minute|मिनट|நிமிட)|jaldi pahunch|reaching soon|வந்துவிடும்)`, it returns the fallback for the caller's language: `"Help is being arranged. Please stay on a high, dry place."` (translated table for ta/hi/te/en in `guard.py`).
**Tests:** bad JSON → `previous` returned; `guard_reply("Stay up high [[FLD-01]]", {"FLD-01"}, None) == ("Stay up high", ["FLD-01"])`; unknown id → fallback; "boat will reach in 10 minutes" with eta None → fallback; same text with eta "20 min" → kept.

### Task 4: PukaarAgent + store
**Files:** `backend/pukaar/agent.py`, `backend/pukaar/store.py`, test `backend/tests/test_agent.py`
**Produces:**
- `Store(path)`: `create_call(lang) -> str`, `add_turn(call_id, Turn)`, `upsert_incident(call_id, facts, latlon, severity) -> Incident` (applies dedup via `should_merge`), `list_incidents(status=None) -> list[Incident]`, `get_incident(id)`, `dispatch(id, team, note, eta) -> Incident`, `resolve(id)`, `queue_callback(call_id, text, lang) -> str`, `pending_callbacks(call_id) -> list[dict]`, `kpis() -> {"calls", "avg_answer_s", "critical_open", "people_affected"}`.
- `Incident` (pydantic): `id, call_ids, facts, lat, lon, loc_source, loc_confidence, severity, status ("new"|"dispatched"|"resolved"), dispatch {team, note, eta} | None, guidance_given: list[str], created_at, updated_at`.
- `PukaarAgent(llm_dialogue, llm_intel, store, places, kb, gps)`: implements the Agent protocol (`user_label="caller"`, `agent_label="pukaar"`, voice `Chetana`). Greeting (auto): Tamil + English + Hindi in one short line, e.g. "பதட்டப்படாதீங்க, நான் உதவறேன். Pukaar helpline. Aap kahan hain?". `on_language` sets `tts_language` and the reply language. `on_user_turn` → `extract_facts` → `merge_facts` → `locate` → `score` → `upsert_incident` → returns `{"type":"incident","incident":...}` (also pushed to `/ws/control` by the app). `reply_sentences` → `next_slot` + `pick_guidance` → LLM → `guard_reply` → records guidance ids.
- `deliver_dispatch(incident)`: if the call is live, the session speaks the dispatch line in the caller's language ("A rescue team is coming. Expected in <eta>.", translated by the LLM, then guard-checked with that eta); otherwise `queue_callback`.
**Tests (with FakeLLM/FakeStt/fake_tts):** one caller turn producing facts → an `incident` event with level and lat/lon; two calls from the same roof → one incident with `len(call_ids) == 2`; dispatch after hang-up → `pending_callbacks` has 1.

### Task 5: FastAPI app
**Files:** `backend/pukaar/app.py`, `run_backend.ps1` (port 8766), test `backend/tests/test_app.py`
**Routes:** `GET /api/health`; `GET /api/places`; `GET /api/incidents?status=`; `GET /api/incidents/{id}`; `POST /api/incidents/{id}/dispatch` `{team, note, eta}`; `POST /api/incidents/{id}/resolve`; `GET /api/kpis`; `GET /api/calls/{id}/callbacks`; `WS /ws/call` (start message `{"type":"start","gps":[lat,lon]|null,"noise_snr_db":null|n}`, then the same audio protocol as Dadi); `WS /ws/control` (pushes `incident`, `kpis`, `call_started`, `call_ended`, `turn` for the selected call); `WS /ws/drill` (Task 7).
**Tests:** dispatch endpoint changes status and emits a control event; callbacks route returns a queued callback after dispatching an ended call; 404s.

### Task 6: Frontend: caller phone + control room
**Files:** `frontend/src/pages/CallerPhone.jsx`, `ControlRoom.jsx`, `IncidentSheet.jsx`, `MapView.jsx` (plain Leaflet in a `useEffect`), `Queue.jsx`, `Kpis.jsx`, `src/net/*.js`; uses `@voice/micCapture`, `@voice/pcmPlayer`.
**Pinned UI:** the design §9 items; pin colours from tokens (critical = rose, high = amber, medium = cyan, low = muted); the pin label shows the caller count when > 1; selecting a queue row flies the map to it and opens `IncidentSheet` with `Drivers` (ui-kit) for severity; the dispatch form (team select: "NDRF Boat 1–4", "Fire & Rescue", "Ambulance 108", "Volunteer boat"; note; ETA) → POST. Layout: desktop = phone left (380 px) + control room right; phone ≤ 900 px = tabs "Call" / "Control room".
**Verify:** `npm run build` passes; manual run with the backend in fake mode (`PUKAAR_FAKE=1` wires FakeLLM/FakeStt/fake_tts) shows a pin appearing after a scripted call.

### Task 7 (P1): Drill mode
**Files:** `backend/pukaar/drill.py`, `backend/pukaar/noise.py`, `frontend/src/pages/Drill.jsx`, test `backend/tests/test_drill.py`
**Produces:** `rain_noise(seconds, hz=8000, seed=0) -> np.ndarray` (brown noise plus random droplet clicks, normalised); `make_case(rng, places) -> Case` (ground-truth `Facts`, language from {ta-IN, hi-IN, en-IN, te-IN}, voice from the 13 v3.0 voices); `async script_for(llm, case) -> list[str]` (2–3 panicked utterances consistent with the facts, in the case language, code-mixed allowed); `async run_drill(n, snr_list, langs, settings, llm, emit) -> dict` (for each case: TTS each utterance (`TtsCache`) → `telephone_band` → `mix_at_snr(rain)` → `transcribe_rest` → `extract_facts` → compare to the truth; strictly one API call at a time); `score_case(truth: Facts, got: Facts) -> dict` with `locality` (bool), `people` (bool), `water_level` (bool), `vulnerable_f1` (float), `severity_level` (bool); `summarise(results) -> {by_snr: {...}, by_lang: {...}}`.
**Tests:** `score_case` exact values on a hand-made pair; `run_drill` with fakes over 2 cases returns per-SNR means; the noise RMS is non-zero and finite.
**UI:** a run button, progress list (case → transcript → facts ✓/✗), and a results table plus `StackedBars` chart by SNR.

### Task 8 (P2): Broadcast alerts
`POST /api/broadcast {text_en, langs[]}` → LLM translation per language → `TtsCache.get_or_make` (container mp3) → returns `[{lang, text, audio_url}]`; UI page with a textarea, language chips and audio players. Test with fakes.

### Task 9: Live tuning, demo, docs
- Live calls in Tamil, Tanglish, Hindi and Telugu; fill `docs/test-log.md`.
- Drill: 12 cases × {20, 10, 5, 0} dB; paste the table into the README.
- `README.md` (what, why, prior art, architecture, Gnani models used, results, setup) and `docs/demo-script.md` (60 s: rain sound → caller in Tamil → pin turns red → dispatcher sends a boat → caller hears it in Tamil → drill accuracy table → "Built on Gnani Prisma + Timbre (+ Evon)").
