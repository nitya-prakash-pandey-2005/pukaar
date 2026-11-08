# Pukaar: design

*Pukaar (पुकार) = "a cry for help".*

## 1. One line
An AI disaster helpline that **answers every call** during floods, cyclones and landslides in the caller's own language, keeps them calm, gives **only approved** safety instructions, triages severity with **explainable rules**, merges duplicate reports, and puts every caller on a **live rescue map**, so a small control-room team can handle a surge of thousands of calls. **A human confirms every dispatch.**

## 2. Why, without sugarcoating
- **The problem is real.** During the Chennai floods (2015, and Cyclone Michaung in 2023), the Kerala floods (2018) and the Wayanad landslides (2024), helplines were overwhelmed exactly when calls mattered most. People turned to social media, and volunteers built spreadsheets and portals by hand (e.g. keralarescue.in in 2018).
- **Prior art exists, so we say it openly.** Bengaluru's "Namma 112" added a multilingual AI language assistant in 2025. Denmark's Corti detects cardiac arrests on emergency calls. US startups (Prepared, Aurelian) triage non-emergency 911 calls. Other hackathon teams have built 112 voice bots.
- **Our honest difference:**
  1. **Disaster surge**, not everyday 112. Pukaar is an **overflow layer**, so no call goes unanswered.
  2. **Grounded safety advice.** The model may only use instruction IDs from an approved NDMA-style list. It cannot invent advice, and every instruction given is logged.
  3. **Explainable severity.** The LLM only extracts facts; a transparent rule table scores urgency. "We don't let an LLM decide who gets rescued first."
  4. **De-duplication.** Five calls about the same rooftop become one incident.
  5. **Callback in the caller's language.** When the dispatcher sends a boat, the caller hears it in Tamil.
  6. **Drill mode with ground truth.** We generate synthetic distress calls with Timbre, bury them in rain noise at 8 kHz, and measure how accurately Prisma plus triage recover the facts. That is measured evidence for the Noise Canceller award.
  7. **Sovereign by design.** Disaster data stays on an Indian stack: Gnani speech, plus Evon's open weights, which a state data centre can host.

## 3. Users
- **Caller**: a frightened person in water, often on a basic phone and a bad network, speaking Tamil, Tanglish, Hindi, Telugu or English.
- **Dispatcher** in the district control room (DEOC / 1077): sees the queue and map, confirms and dispatches.
- **Rescue teams** (NDRF/SDRF, fire, volunteers): receive dispatches.
- **District officer**: sends broadcast alerts in every language.

## 4. Goals, non-goals, anti-goals
**Goals (P0):** a live voice call with Pukaar in the browser; real-time triage card; incident on the map; severity queue; dispatch with a voice callback to the caller.
**P1:** drill mode with an accuracy table by noise level and language. **P2:** multilingual broadcast alerts; Evon for triage.
**Non-goals:** real telephony; integration with real 112/ERSS systems; real GPS (we simulate the location a phone would share).
**Anti-goals:**
- The AI dispatching on its own.
- The AI promising an arrival time that a human did not confirm.
- Invented medical or safety advice.
- Real personal data, or calls labelled as real. Every screen shows **"Simulated emergency call: synthetic data"**.

## 5. Demo scenario
"A flood night in Chennai." Callers from Velachery, Mudichur, Pallikaranai and Tambaram speak Tamil, Tanglish, Hindi (migrant workers) and Telugu. The control-room map is centred on Chennai (13.0827, 80.2707).

## 6. How a call works
```
Caller phone (browser mic, 8 kHz) ──WS──► backend
   VoiceAgentSession (voice-core) ──► Prisma v3.0 stream (indic-auto hints ta-IN,hi-IN,en-IN,te-IN; codemix; disaster keyterms)
   PukaarAgent
     ├─ on_user_turn: Triage extractor (LLM JSON) → merge facts → gazetteer locate → severity rules → dedup → upsert Incident → broadcast to the control room
     ├─ reply: slot planner picks the ONE most important missing fact + up to ONE approved instruction → LLM writes a calm 1–2 sentence reply in the caller's language
     └─ voice: Timbre v3.0 "Chetana" (warm, healthcare), speed 0.95, <slow> for instructions
Control room (browser) ──WS /ws/control──► incidents, calls, KPIs; dispatcher actions → REST → callback speech to the caller
```

## 7. Triage model
`Facts` (all optional): `locality`, `landmark`, `lat`, `lon`, `hazard` (flood|cyclone|landslide|fire|building_collapse|medical|other), `people_count`, `trapped`, `on_roof`, `water_level` (none|ankle|knee|waist|chest|neck), `vulnerable` ⊆ {infant, child, elderly, pregnant, disabled, sick}, `injuries` ⊆ {bleeding, fracture, unconscious, burn, other}, `medical_needs` ⊆ {oxygen, labour, dialysis, insulin, medication}, `needs` ⊆ {boat, ambulance, food, water, medicine, evacuation}, `caller_language`.

**Severity rules** (score 0–100, capped; each addition becomes a "driver" bar in the UI):

| Fact | Points |
|---|---|
| hazard base | flood 20 · cyclone 20 · landslide 35 · fire 35 · building_collapse 40 · medical 25 · other 10 |
| water_level | ankle 2 · knee 8 · waist 18 · chest 30 · neck 35 |
| trapped / on_roof | +15 / +10 |
| vulnerable (cap 25) | infant 12 · pregnant 12 · elderly 8 · disabled 8 · sick 8 · child 6 |
| medical_needs (cap 25) | oxygen 20 · labour 20 · dialysis 12 · insulin 10 · medication 5 |
| injuries | unconscious 25 · bleeding 20 · fracture 12 · burn 12 · other 8 (take the max, not the sum) |
| people_count | +min(10, 1.5 × people) |

Level: **critical ≥ 70 · high ≥ 45 · medium ≥ 25 · low < 25**.

**Slot priority** (the agent asks for the first missing one): `location` (locality or landmark) → `people_count` + `trapped` → `injuries`/`medical_needs` → `water_level` → `vulnerable` → done (reassure, give an instruction, keep the line open).

**Dedup:** merge into an existing open incident when hazard matches and either (distance < 300 m) or (same locality and landmark similarity ≥ 0.7), within 3 hours. A merged incident keeps the max severity facts, counts distinct callers, and lists all call ids.

## 8. Approved guidance (`backend/data/guidance_kb.json`)
About 15 entries `{id, hazards[], when (water_level or condition), text_en}`. Examples:
- FLD-01 "Move to the highest floor or the roof. Take drinking water, medicines, your phone and a torch."
- FLD-02 "If it is safe to reach, switch off the electricity mains."
- FLD-03 "Do not walk or drive through moving water. Even ankle-deep flowing water can knock you down."
- FLD-04 "Stay away from electric poles and fallen wires."
- FLD-05 "Signal rescuers from the roof with a bright cloth or a torch."
- FLD-06 "Save your phone battery: close other apps, and send an SMS if calls fail."
- FLD-07 "Drink only boiled or bottled water."
- MED-01 "Press a clean cloth firmly on any bleeding wound."
- MED-02 "Keep insulin dry and as cool as possible. If sugar feels low, eat something sweet."
- MED-03 "Lay an unconscious person on their side and keep their airway clear."
- CYC-01 "Stay indoors, away from windows, until officials announce it is safe."
- LND-01 "Move away from the slope and river channels. Listen for cracking trees or rolling stones."
- GEN-01 "Your details are recorded and the control room can see you on the map." (Never promise a time.)
- GEN-02 "Stay calm and stay on a high, dry place. Keep this phone with you."

The LLM receives at most 2 candidate entries (filtered by hazard and water level, not already given) and must output the chosen id in a tag `[[FLD-03]]` that we strip from the speech and log.

## 9. Screens
1. **Caller phone:** call button, language "Auto", a **simulated location** picker (a locality from the gazetteer, randomly jittered within 150 m, like a phone's emergency location), a noise slider ("Rain/wind"), the earphones hint, the disclaimer, live captions.
2. **Control room:** KPI row (calls answered · average answer time · critical open · people affected), a **Leaflet map** (dark CARTO tiles) with severity-coloured pins and caller counts, the queue sorted by severity, an incident detail sheet (facts, severity drivers, transcript, guidance ids given, calls merged), and dispatch actions (team, note, ETA) → **callback speech**.
3. **Drill:** choose N calls (default 12), SNR set {20, 10, 5, 0} dB and languages → live progress → accuracy table (locality, people, water level, vulnerable F1, severity level) per SNR and language.
4. **Broadcast (P2):** English alert → translated and spoken in chosen languages → playable audio list.

## 10. Calls made (by the designer)
- Leaflet (plain, not react-leaflet) is the only extra UI dependency. A map is unavoidable and the ui-kit has none.
- The gazetteer is built once from OpenStreetMap Nominatim (1 request per second, generic User-Agent) and committed as JSON, so it works offline.
- Triage uses `LLM(settings, purpose="intel")`, so Evon can take it over when hosted.
