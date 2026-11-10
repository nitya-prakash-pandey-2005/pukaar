<div align="center">

<img src="docs/brand/banner.png" alt="Pukaar · पुकार · புகார் — When every line is busy, Pukaar picks up." width="100%">

**Pukaar answers overflow emergency calls in the caller's own language, keeps them calm, asks the questions a rescuer needs, and puts every caller on a live rescue map. A human confirms every dispatch.**

![Gnani Prisma v3.0](https://img.shields.io/badge/Gnani-Prisma%20v3.0%20STT-0e7490)
![Gnani Timbre v3.0](https://img.shields.io/badge/Gnani-Timbre%20v3.0%20TTS-2563eb)
![Tests](https://img.shields.io/badge/tests-277%20passing-16a34a)
[![CI](https://github.com/nitya-prakash-pandey-2005/pukaar/actions/workflows/ci.yml/badge.svg)](https://github.com/nitya-prakash-pandey-2005/pukaar/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61dafb?logo=react&logoColor=black)
![CAP 1.2](https://img.shields.io/badge/alerts-CAP%201.2-f59e0b)

**Live demo:** [pukaar-snowy.vercel.app](https://pukaar-snowy.vercel.app/) · **Video:** *[video link]* · **[One-page pitch (PDF)](PITCH.pdf)** · [PITCH.md](PITCH.md) · [Combined pitch: three products, one Gnani engine](https://github.com/nitya-prakash-pandey-2005/dadi-vs-scammers/blob/main/docs/THREE-PRODUCTS.md)<br>
Sister repos: [Dadi vs Scammers](https://github.com/nitya-prakash-pandey-2005/dadi-vs-scammers) · [Apni Awaaz](https://github.com/nitya-prakash-pandey-2005/apni-awaaz) · [Run it locally](#run-it)

<img src="docs/screenshots/product/desktop-overview.png" alt="Pukaar: the caller phone, live KPIs and the rescue map with severity-coloured pins" width="900">

<sub>Every screenshot is from a live run on Gnani Prisma and Timbre (10 Nov 2026) with synthetic callers. No real emergency data.</sub>

</div>

---

## Contents

[The problem](#the-problem) · [What it does](#what-it-does) · [Screens](#screens) · [Wireframe](#wireframe) · [How it works](#how-it-works) · [How it's different](#how-its-different) · [Gnani models used](#gnani-models-used) · [Measured results](#measured-results) · [Safety by design](#safety-by-design) · [How we would make it more advanced](#how-we-would-make-it-more-advanced) · [Run it](#run-it) · [Tests](#tests) · [Team and family](#team-and-family) · [Project docs](#project-docs)

---

## The problem

When a city floods, the helplines fill up first. Every helpline has a fixed number of call-takers, and a flood brings every call at once.

- **Chennai, Cyclone Michaung, December 2023.** "Almost every call to the complaint cell went unanswered till December 7," and power and mobile networks were down for three to four days ([DT Next](https://www.dtnext.in/news/city/calls-to-govt-helplines-go-unanswered-754073), 13 Dec 2023). Residents who could not reach the GCC 1913 helpline or its WhatsApp number turned to Twitter, where GCC replied by asking them to call the helpline ([The News Minute](https://www.thenewsminute.com/tamil-nadu/chennai-floods-helplines-inundated-people-struggle-to-contact-authorities), 4 Dec 2023).
- **Kerala floods, August 2018.** 483 people died and 14.50 lakh people were in more than 3,000 relief camps at the peak ([Morung Express/IANS](https://morungexpress.com/483-dead-flood-loss-more-keralas-annual-outlay-vijayan), 30 Aug 2018). Volunteers built keralarescue.in in about a day; some 1,500 volunteer developers ran it, and it received over 1 crore aid and rescue requests ([ThePrint](https://theprint.in/governance/behind-official-kerala-rescue-website-are-1500-techies-working-for-free/102568), 22 Aug 2018). One person "called 10 numbers and none of them answered" ([The Caravan](https://caravanmagazine.in/vantage/how-social-media-was-vital-to-rescue-efforts-during-the-kerala-floods), 6 Oct 2018).
- **Chennai floods, December 2015.** About 300 people died, according to the CAG audit ([The News Minute](https://www.thenewsminute.com/article/cag-report-slams-chennai-administration-2015-floods-says-govt-was-unprepared-84476), 10 Jul 2018). Rescue was crowdsourced through #ChennaiRainsHelp and a volunteer database ([Mongabay](https://news.mongabay.com/2015/12/chennairainshelp-torrential-downpour-floods-indian-city-twitter-users-crowdsource-help/), 2 Dec 2015).

The pattern repeats: the official line is busy, so people fall back to social media, spreadsheets and volunteer websites, and the control room loses sight of them. India's 112 line has handled 26–29 crore calls since launch ([Keekli](https://keekli.in/child-helpline-integrated-with-erss-112-in-9-states/), [Outlook](https://www.outlookindia.com/national/29-crore-calls-handled-by-national-emergency-response-helpline-112-so-far-officials-news-294218), 2023), and Bengaluru reported "call congestion, dropped connections" at peak hours on its old phone system ([IBTimes](https://www.ibtimes.co.in/namma-112-review-how-bengaluru-rebuilt-its-emergency-response-system-over-four-years-897110), 29 Jan 2026).

**Pukaar is an overflow layer.** When every human call-taker is busy, the call does not ring out. Pukaar picks up, in Tamil, Tanglish, Hindi, Telugu or English, and the control room sees the caller on the map within seconds.

---

## What it does

| | Feature | In one line |
|---|---|---|
| 1 | **Answers the call, in the caller's language** | Prisma transcribes code-mixed 8 kHz phone audio; Timbre replies in the same language, one question at a time. |
| 2 | **Severity you can explain** | The LLM only extracts facts; a fixed rule table scores 0–100 and shows every point. |
| 3 | **One rescue map, no duplicates** | Spoken landmarks and phone location put the caller on the map; reports within 300 m and 3 h merge. |
| 4 | **No voice? Send a text** | An SMS goes through the same triage and gets the next question back. |
| 5 | **Human dispatch, heard in the caller's language** | A dispatcher confirms team and ETA; the caller hears it live or as a missed callback. |
| 6 | **Broadcast alerts in 7 languages, as CAP 1.2** | One English alert, spoken by Timbre in 7 languages and exported as CAP 1.2 XML. |
| 7 | **A noise drill, built in** | Synthetic calls buried in rain show what noise costs, language by language. |
| 8 | **Which team, where, and a one-page SitRep** | Suggests the best free rescue team with its reasons, plans the whole queue, rings hotspots on the map and prints a district situation report. A human still confirms every dispatch. |
| 9 | **Rescuer interpreter** | A rescue team from another state speaks Hindi or English; the trapped caller hears it in Tamil, Telugu, Hindi or English (Timbre), and the answer comes back translated, with captions in both languages. Machine interpretation, one side at a time. |

### 1. Answers the call, in the caller's language

The caller speaks the way people speak in a flood: fast, mixed languages, rain in the background. Gnani **Prisma v3.0** transcribes the 8 kHz phone audio with automatic Indic language detection and code-mix output. Pukaar replies with Gnani **Timbre v3.0** in the same language: one line of reassurance, at most one approved safety instruction, and one question.

It asks in a fixed order, the order a rescue team needs: **where are you → how many people → anyone hurt or needing medicine → how high is the water → anyone old, pregnant, a baby, sick or disabled**.

### 2. Severity you can explain, point by point

The LLM only **extracts facts** (hazard, water level, people, injuries, vulnerable people, medical needs). A fixed rule table turns those facts into a 0–100 score: critical at 70 and above, high at 45. Every point is shown as a driver bar, so a dispatcher can see exactly why one rooftop outranks another.

> We don't let an AI decide who gets rescued first. It fills in a form; the rules rank; a human decides.

### 3. One rescue map, no duplicates

Pukaar locates callers two ways: the phone's emergency location (simulated in the demo) and the landmarks they say ("near the Vijayanagar bus stop"), matched against a Chennai gazetteer of 42 localities with Tamil aliases. Reports within 300 m and 3 hours about the same hazard merge into one incident, so five calls about one rooftop become one pin with a caller count. A merged report can raise an incident's water level but never lower it.

The **flood-night surge** button replays 24 synthetic callers in four languages through the real triage, from a committed recording, so it costs no tokens and no Gnani credits.

### 4. No voice? Send a text

Weak network, a speech-impaired caller, a jammed line: one text message goes through the same triage and lands on the same map, and Pukaar texts back the next question it needs answered. The `/api/sms` endpoint is where an SMS or WhatsApp gateway would post; in the demo, the caller phone's SMS box sends it.

### 5. Human dispatch, heard in the caller's language

The dispatcher picks a team, types an ETA and confirms. Only then may Pukaar mention a time. The caller hears the confirmation in their own language: live if they are still on the line, or as a **missed callback** they can play later. The dispatcher can also type a plain English message ("The boat is at the temple gate. Wave a white cloth.") and every caller of that incident hears it translated.

**Missed-call mode:** no balance? Give a missed call. The pin appears at once and Pukaar calls back.

### 6. Broadcast alerts in 7 languages, exported as CAP 1.2

A district officer types one English alert. Pukaar translates it in a single LLM call and Timbre speaks it in Tamil, Hindi, Telugu, Malayalam, Kannada, Bengali and English. Place names are masked as `{P1}` before translation and restored from the gazetteer, so "Adyar" stays அடையாறு (without the mask, the model once wrote "Aadhaar river").

The alert downloads as **CAP 1.2 XML**, one `<info>` block per language. CAP is the OASIS standard that India's SACHET alert platform is built on.

### 7. A noise drill, built in

Synthetic distress calls are spoken by Timbre, cut to an 8 kHz phone band, buried in rain at 0–20 dB, transcribed by Prisma and triaged. The results card in the control room shows what noise costs, language by language.

### 8. Which team, where the hotspots are, and a one-page SitRep

Decision support for the dispatcher, all plain rules over a **synthetic roster of 10 teams** (NDRF/SDRF and volunteer boats, fire & rescue, 108 ambulances, a medical team) based at gazetteer localities ([`backend/data/teams.json`](backend/data/teams.json)):

- **Recommended teams.** The incident sheet ranks the free teams out of 100: the right kind of team for the facts (50: a boat for waist-deep water or people trapped or on a roof, an ambulance or medical team for injuries and medical needs, fire & rescue for fire, collapse and landslide), room for everyone reported (15) and ETA (35: straight line × 1.3 at the team's speed, plus 5 minutes to leave). Every suggestion says why, e.g. "boat · 3.2 km · ~30 min · carries 4 of 8, more trips needed · water chest-high". An ambulance is never sent into waist-deep water. **"Dispatch this team" only fills the dispatch form** with the team and ETA; the dispatcher checks and confirms.
- **Plan all.** One suggested team per waiting incident, most severe first, then the longest waiting, never the same team twice. Incidents with no free team that fits, or with no location, are listed for a human decision instead of guessed.
- **Hotspots.** Open incidents within 500 m of each other are grouped (single linkage) and shown as soft circles sized by people and coloured by the worst severity, with a list in the control room.
- **SitRep.** A district situation report: calls, incidents by severity, waiting / dispatched / resolved, people affected, households with elderly people, children, medical needs or disability, trapped and on-roof counts, how long critical incidents have waited, top localities and a recent timeline. It prints to PDF and downloads as Markdown.

Read-only endpoints: `GET /api/teams`, `/api/incidents/{id}/recommend`, `/api/plan`, `/api/hotspots`, `/api/sitrep`. Dispatch still goes through `POST /api/incidents/{id}/dispatch`.

---

### 9. Rescuer interpreter

Rescue teams sent from other states often do not speak the caller's language: an NDRF boat crew from the north may speak Hindi, the woman on a roof in Velachery speaks Tamil. The **Interpreter** page (also linked from every incident as "Talk to the caller through the interpreter") puts two push-to-talk buttons on one screen, one per side, each with its own language (rescuer: Hindi or English; caller: Tamil, Telugu, Hindi or English).

Each turn: the clip goes to Prisma with **one locale** (the speaker's), **one short LLM call** translates it, and Timbre speaks it in the listener's language (the caller hears "Chetana", the rescuer "Prakash"). Both sides see the original and the translation side by side, with the time of each step. One side talks at a time (a server-side speaking lock); pressing while the other side's translation is still playing stops it (barge-in).

The translation is checked like everything Pukaar says: it may not add a time promise, a number or a "you are safe" that the speaker did not say (`guard.adds_nothing`), and it may not drop a number the speaker did say. If it fails, the listener hears the speaker's own words and both captions say why. The page is labelled **machine interpretation**.

Live check (10 Nov, synthetic voices, [`docs/test-log.md`](docs/test-log.md)): Hindi → Tamil and Tamil → Hindi, with the landmark, the floor and the head count kept; the translated audio was ready **1.6–2.3 s** after the speaker released the button (Timbre rendering the whole clip is the largest part). The static demo replays this exchange with its real audio.

## Screens

All from the live run of 10 Nov 2026 (real Gnani + Groq, synthetic callers). Desktop at 1440 px, phone at 390 px.

**A live Tamil call:** captions on the caller phone, the incident marked live in the queue.

<p>
<img src="docs/screenshots/product/desktop-live-call.png" alt="A live Tamil call: captions on the caller phone, the incident marked live in the queue" width="610">
<img src="docs/screenshots/product/mobile-live-call.png" alt="The same live call at phone width" width="200">
</p>

**Why this severity:** driver bars, facts and the approved guidance given.

<p>
<img src="docs/screenshots/product/desktop-incident-severity.png" alt="Incident sheet: why this severity, facts, approved guidance given" width="610">
<img src="docs/screenshots/product/mobile-incident-severity.png" alt="Incident sheet at phone width" width="200">
</p>

**Control room after a surge:** KPIs, merged pins and the severity queue.

<p>
<img src="docs/screenshots/product/desktop-control-room.png" alt="Control room after a surge: KPIs, the rescue map with merged pins and the severity queue" width="610">
<img src="docs/screenshots/product/mobile-map-queue.png" alt="Rescue map and queue at phone width" width="200">
</p>

**SMS intake:** a Tamil text, and Pukaar's Tamil reply asking for the next missing fact.

<p>
<img src="docs/screenshots/product/desktop-sms-typed.png" alt="A Tamil SMS typed on the caller phone" width="405">
<img src="docs/screenshots/product/desktop-sms-reply.png" alt="Pukaar's Tamil reply asks the next missing fact; the texter is on the map" width="405">
</p>

**Human dispatch:** NDRF Boat 1, ETA 40 min, and a box to message the caller.

<p>
<img src="docs/screenshots/product/desktop-incident-dispatched.png" alt="The SMS incident dispatched: NDRF Boat 1, ETA 40 min, and a box to message the caller" width="610">
</p>

**Broadcast and CAP 1.2:** one English alert spoken in Tamil, Hindi, Telugu and English, and the exported XML.

<p>
<img src="docs/screenshots/product/desktop-broadcast.png" alt="One English alert spoken in Tamil, Hindi, Telugu and English" width="610">
<img src="docs/screenshots/product/mobile-broadcast.png" alt="Broadcast card at phone width" width="200">
</p>

<p>
<img src="docs/screenshots/product/desktop-cap-export.png" alt="The exported CAP 1.2 XML: status Exercise, one info block per language" width="610">
</p>

**Recommended teams and the one-page SitRep** (static demo build, computed from the same recorded incidents): "Dispatch this team" filled the form; the dispatcher still confirms.

<p>
<img src="docs/screenshots/product/desktop-recommended-teams.png" alt="Incident sheet: three recommended teams with reasons, and the dispatch form filled with the best one and its ETA" width="610">
</p>

<p>
<img src="docs/screenshots/product/desktop-sitrep.png" alt="District situation report: totals, severity, status, vulnerable households and hotspots by locality" width="610">
</p>

**Noise drill results card.**

<p>
<img src="docs/screenshots/product/desktop-noise-drill.png" alt="Noise drill results card" width="610">
<img src="docs/screenshots/product/mobile-noise-drill.png" alt="Noise drill at phone width" width="200">
</p>

---

## Wireframe

The two screens and the path one call takes between them. Teal arrows are automated (Gnani, the LLM and the rules); amber arrows are human decisions.

<img src="docs/design/wireframe.svg" alt="Low-fidelity wireframe: the caller phone (call, missed call, SMS, location, noise, captions, callback) and the control room (KPIs, rescue map, severity queue, incident sheet with dispatch, broadcast with CAP export, noise drill), linked through the server path Prisma → LLM facts → rules → guard → Timbre" width="100%">

<sub>Source: [`docs/design/wireframe.svg`](docs/design/wireframe.svg), generated by [`scripts/make_wireframe.py`](scripts/make_wireframe.py).</sub>

---

## How it works

### Architecture

```mermaid
flowchart TB
    caller(["Caller<br/>browser mic, 8 kHz"]) -->|"/ws/call"| prisma["Gnani Prisma v3.0<br/>indic-auto, codemix, keyterms"]
    sms(["SMS / WhatsApp text"]) -->|"/api/sms"| extract
    prisma --> extract["LLM fact extraction<br/>Groq qwen3.8-27b"]
    extract --> rules["Severity rule table<br/>0-100, drivers"]
    extract --> locate["Locate<br/>GPS + gazetteer landmarks"]
    rules --> dedup{"Dedup<br/>300 m, 3 h, same hazard"}
    locate --> dedup
    dedup --> incident[("Incident store")]
    extract --> reply["Reply: next missing fact<br/>+ max 1 approved instruction"]
    reply --> guard{"Guard<br/>no time promises,<br/>no 'you are safe',<br/>approved IDs only"}
    guard --> timbre["Gnani Timbre v3.0<br/>Chetana voice"]
    timbre --> caller
    incident -->|"/ws/control"| room["Control room<br/>map, queue, KPIs"]
    room -->|"human confirms"| dispatch["Dispatch + ETA"]
    dispatch --> callback["Callback in the<br/>caller's language"]
    callback --> timbre
    room --> broadcast["Broadcast alert<br/>7 languages"]
    broadcast --> timbre
    broadcast --> cap["CAP 1.2 XML"]
```

### One caller, step by step

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller phone
    participant S as Pukaar server
    participant P as Gnani Prisma v3.0
    participant L as LLM (Groq qwen3.8-27b)
    participant T as Gnani Timbre v3.0
    participant R as Control room
    actor D as Dispatcher
    C->>S: 8 kHz PCM over /ws/call
    S->>P: stream audio (indic-auto, codemix, keyterms)
    P-->>S: transcript of the turn (e.g. Tamil script)
    S->>L: extract facts (one extraction per turn)
    L-->>S: hazard, water level, people, vulnerable, medical, landmarks
    par Reply to the caller
        S->>L: reply: next missing fact + at most 1 approved guidance ID
        L-->>S: reply text (not streamed: the guard sees all of it)
        S->>S: guard: no "you are safe", no time unless an ETA is confirmed, known IDs only, else the safe line
        S->>T: speak in the caller's language (Chetana)
        T-->>C: reply audio
    and Update the control room
        S->>S: rule table score 0-100, locate (GPS, gazetteer), dedup (300 m, 3 h)
        S-)R: incident upsert over /ws/control (pin, queue, drivers)
    end
    D->>R: pick team, type ETA, confirm
    R->>S: dispatch
    S->>L: translate the confirmation (a translation that adds a time, a number or "you are safe" is dropped)
    S->>T: speak it in the caller's language
    T-->>C: live if still on the line, else a missed callback
```

1. The browser streams the caller's microphone as 8 kHz PCM over `/ws/call`. Optional rain is mixed in to test noise.
2. Prisma transcribes each turn. The LLM extracts facts and merges them with what the caller said before.
3. Facts are located (phone GPS, then spoken landmarks against the gazetteer), scored by the rule table and merged into an existing incident if one is close enough.
4. The reply asks for the next missing fact and may add one instruction from the approved list. The guard checks it before Timbre speaks.
5. The control room receives every change over `/ws/control`. Dispatch, messages, callbacks and broadcasts go back to callers through Timbre.

---

## How it's different

| | Answers the call itself | Indian languages, code-mix | Severity ranking | Merges duplicates | Speaks back in the caller's language | CAP 1.2 alerts |
|---|---|---|---|---|---|---|
| **ERSS-112** (C-DAC) | No: human call-takers | Not described | Not described | Not described | Not described | Not described |
| **NDMA SACHET** (C-DOT) | No: one-way alerts, citizens cannot call in | 19+ languages (alerts) | n/a | n/a | n/a | Yes, CAP-based |
| **Bengaluru Namma 112 "VANKI"** (Apr 2026) | No: live translation for human call-takers | 10+, incl. Tamil, Telugu, Malayalam | Not reported | Not reported | Via the call-taker | Not reported |
| **Telangana AI-ERSS** (Aug 2026) | No: assists call-takers | Not reported | Yes | Yes | Not reported | Not reported |
| **RapidSOS UNITE** (US) | No: 911 co-pilot | Translation ("240+ dialects", vendor claim), US device data | Not reported | Not reported | Not reported | Not reported |
| **Carbyne / Axon** (US) | No: "augments" human staff | "70+ languages", no Indian ones named | AI triage | Yes | Not reported | Not reported |
| **Corti** (Denmark) | No: prompts dispatchers | Not reported | Cardiac-arrest alerts (model) | Not reported | Not reported | Not reported |
| **Pukaar** | **Yes, on overflow** | **Tamil, Tanglish, Hindi, Telugu, English** | **Fixed rule table, shown as drivers** | **Yes, 300 m / 3 h, same hazard** | **Yes: live, or as a missed callback** | **Yes, 7 languages** |

Sources: [ERSS-112](https://police.tripura.gov.in/112-police-helpline), [SACHET](https://taxguru.in/corporate-law/india-deploys-mobile-alert-system-due-rising-disaster-preparedness.html), [VANKI](https://www.devdiscourse.com/article/technology/3890691-bengaluru-police-launch-multilingual-ai-capability-in-112-emergency-response-system), [Telangana AI-ERSS](https://www.siasat.com/telangana-police-launches-ai-enabled-emergency-response-system-3519196/), [RapidSOS](https://rapidsos.com/rapidsos-unite-for-911/), [Axon Prepared AI](https://www.axon.com/products/prepared-ai), [Corti trial](https://pmc.ncbi.nlm.nih.gov/articles/PMC7788469).

Duplicate filtering and severity ranking are not new: Telangana's AI-ERSS does both, and Bengaluru's VANKI already translates Tamil and Telugu for call-takers. What we have not seen is the combination.

> **To our knowledge, as of November 2026,** the Indian AI deployments in emergency calls we found (Bengaluru VANKI, Telangana AI-ERSS) assist human call-takers. We found no public deployment of an AI voice agent that itself answers overflow disaster calls in code-mixed Tamil, Hindi and English, triages with explainable rules, guards against false reassurance, and emits CAP 1.2 alerts.

One lesson we took from Corti: in a Copenhagen trial of 169,049 calls, its model spotted cardiac arrest more often than dispatchers, but alerting dispatchers did not significantly improve their recognition ([JAMA Netw Open](https://pmc.ncbi.nlm.nih.gov/articles/PMC7788469), 2021). A black box that is right is not enough; people have to be able to trust it. That is why Pukaar's ranking is a rule table anyone can read.

---

## Gnani models used

| Model | Where | Settings (from the code) |
|---|---|---|
| **Prisma v3.0** (`prisma-v3.0`), realtime WebSocket | Live calls | `language_code: indic-auto`, `format: codemix`, 8 kHz PCM, keyterms = flood words plus every gazetteer locality |
| **Prisma v3.0**, REST | Noise drill | same model, `indic-auto`, Pukaar keyterms |
| **Prisma v3.0**, REST | Rescuer interpreter | one locale per side (the speaker's: `hi-IN`, `en-IN`, `ta-IN` or `te-IN`), 16 kHz push-to-talk clips |
| **Timbre v3.0** (`timbre-v3.0`) | Every reply, greeting and filler | voice "Chetana", speed 0.95, raw PCM at 8 kHz; greeting and fillers pre-rendered once and cached |
| **Timbre v3.0** | Broadcast alerts, callbacks | MP3 at 24 kHz for broadcasts; PCM for callbacks; cached by text |
| **Timbre v3.0** | Rescuer interpreter | the caller hears "Chetana", the rescuer "Prakash"; WAV at 24 kHz, cached by text |
| **Timbre v3.0** | Noise drill and demo callers | other Timbre voices (for example "Prakash") speak the synthetic callers |

**LLM:** Groq `qwen/qwen3.8-27b` for fact extraction, replies and translation. The adapter also supports **Gnani Evon v3.3** through an OpenAI-compatible endpoint (`LLM_PROVIDER=evon`, see [`docs/EVON-HOSTING.md`](docs/EVON-HOSTING.md)); we did not host Evon for the demo.

The shared voice engine (`voice-core/`, synced from [Dadi vs Scammers](https://github.com/nitya-prakash-pandey-2005/dadi-vs-scammers)) handles streaming STT, barge-in, a half-duplex echo guard, a request gate with 429 retries, reconnect backoff and a TTS stall timeout.

---

## Measured results

All numbers come from [`docs/test-log.md`](docs/test-log.md) and [`docs/drill-results.md`](docs/drill-results.md). Small samples; conditions stated.

**Live run for these screenshots (10 Nov 2026, 18:55–19:05 IST, real Gnani + Groq)**: three calls from a synthetic Tamil caller (three lines spoken by Timbre "Prakash" and fed into Chrome's microphone in real time), two SMS, one surge replay, one dispatch, two broadcasts.
- Prisma wrote every caller line in Tamil script with the meaning intact (small normalisations such as நாங்க → நாங்கள்).
- Severity reached **critical 90**: flood +20, chest-deep water +30, on the roof +10, elderly and child +14, insulin +10, 4 people +6. Every call merged into the same Velachery incident (4 callers, one of them from the surge).
- LLM time to the first reply sentence, averaged by the control room: **0.72–1.05 s**.
- A Tamil SMS (Mudichur, 5 people on a roof, waist-deep water, a pregnant woman) scored **high 68**, was located, and got a Tamil reply asking about injuries and medicines.
- The broadcast was spoken by Timbre in Tamil, Hindi, Telugu and English; the Tamil text kept அடையாறு. No 429 errors in the server log.

**First live call (8 Nov 2026, real Gnani + Groq, 4 Tamil caller lines spoken by Timbre and streamed in real time)**
- Prisma streaming transcript latency: **90–133 ms**.
- Reply audio started about **2.0 s** after the caller stopped (end of speech + fact extraction ~0.45 s + reply ~0.3 s + first TTS chunk). Greeting and fillers are now pre-rendered, so a reply never starts with silence.
- Triage reached **critical 84** on "water up to the chest"; transcripts were exact.

**Noise drill (6 synthetic calls × clean, 20, 10, 5, 0 dB rain, 8 kHz band, Prisma REST `indic-auto`)**

| SNR | Transcript CER (same script) | Locality | People count | Vulnerable F1 | Severity level |
|---|---|---|---|---|---|
| clean | 7.5% | 67% | 100% | 100% | 67% |
| 10 dB | 23.2% | 67% | 100% | 100% | 67% |
| 0 dB (rain as loud as the voice) | 10.8% | 67% | 83% | 100% | 67% |

Triage accuracy was flat from clean audio to 0 dB: locality, vulnerable people and severity level scored the same at 0 dB as on clean audio. Tamil transcripts stayed at about 3–7% CER even at 0 dB. The clean row is the baseline; its misses come from LLM extraction, not audio.

**SMS intake (live Groq)**: a Tamil SMS (Velachery, 4 on the roof, chest-deep water, grandmother needs insulin) scored **critical 84**; a Hindi SMS (Saidapet, 3 people, waist-deep, sick child) scored **high 57**, located by landmark.

**Groq budget per live turn**: about 1,000 tokens (extraction ~530 + reply ~470), so one live call fits the free tier's 8k tokens/min.

### Known limits

- The drill is small (6 calls per noise level). Treat its percentages as a smoke test, not a benchmark.
- The gazetteer covers 42 Chennai localities. Another city needs its own gazetteer file.
- A romanised SMS ("paani kamar tak") has no script to detect. In the live run, a romanised-Hindi SMS that named a Chennai locality was tagged Tamil by the LLM and answered in Tamil. Common Hindi and Tamil words now decide first and the LLM's guess second; other romanised languages still rely on the LLM.
- Hindi and Telugu broadcasts keep place names in Latin script ("Adyar"); only Tamil aliases are in the gazetteer.
- Phone location is simulated in the browser. A real deployment would take it from the telecom emergency location feed.

---

## Safety by design

- **No false reassurance.** The guard blocks "you are safe" in English, Hindi, Tamil and Telugu, and any arrival time ("10 minutes", "jaldi pahunch", "10 நிமிஷத்துல வருவோம்", "help will come soon") unless a dispatcher has confirmed an ETA. A blocked reply is replaced by a safe fallback line.
- **Approved guidance only.** The model may cite advice only by ID from 16 entries in [`backend/data/guidance_kb.json`](backend/data/guidance_kb.json) (flood, medical, cyclone, landslide, fire, collapse, general), at most one per reply. A reply that cites an unknown ID or a broken tag is replaced by the safe line. Flood advice such as "go to a high place" is never given to fire, landslide or collapse callers.
- **Translations add nothing.** A translated dispatch or message that adds a time, a number or "you are safe" is not sent; the caller hears the dispatcher's own words instead.
- **A human confirms every dispatch.** Pukaar never sends a team. It ranks the queue, suggests teams with their reasons, fills the form and relays the dispatcher's decision.
- **When in doubt, the safe line.** If the LLM fails, returns nothing or is blocked, the caller hears a fixed line in their language: "Help is being arranged. Please stay on a high, dry place." (only the first sentence for fire, landslide or collapse).
- **Synthetic data only.** The caller phone says "Simulated emergency call: synthetic data". Every caller in this repo, the surge recording, the drill and these screenshots is synthetic.
- **CAP alerts are marked `Exercise`**, not `Actual`, and validate against the official OASIS CAP 1.2 schema ([review notes](docs/review-cl-2026-11-10.md)).

<p>
<img src="docs/screenshots/product/mobile-guard-fallback.png" alt="Live call: the caller's lines in Tamil, then Pukaar's safe fallback line" width="220">
</p>

---

## How we would make it more advanced

What we would build next, in order, and why. None of this is in the repo today.

| Next step | What we would do | Why |
|---|---|---|
| **1. Real telephony** | Put Pukaar behind a real number through a cloud telephony provider such as Exotel that can stream call audio to a WebSocket, as an overflow route that only takes calls a human line rejects as busy or unanswered. Later, the same overflow hook on a state's 112 (ERSS) or a city helpline such as GCC 1913, which needs the operator's agreement. | Today the caller is a browser microphone. `/ws/call` already takes 8 kHz PCM, the phone-line format, so the engine does not change; what changes is who can reach it. Routing only overflow keeps humans first. |
| **2. Real caller location** | Take location from the telecom emergency location feed instead of the simulated browser location, and keep spoken landmarks as the cross-check. | The map is only as good as the pin. In the noise drill, locality was right for 67% of calls, the weakest triage number, and a gazetteer only knows the places in it. |
| **3. SACHET / CAP feeds** | Read official CAP warnings for the district (the standard SACHET is built on) so Pukaar knows which areas are under a red alert, and hand our CAP 1.2 `Exercise` alerts to the alerting authority for review instead of only downloading them. | Pukaar already writes CAP 1.2; it does not read it. An incoming warning should raise the priority of calls from the warned area, and an officer should approve before anything goes out as `Actual`. |
| **4. GIS flood layers** | Overlay flood-inundation, road-closure and relief-camp layers on the rescue map, and add "inside a mapped flood zone" as one more line in the rule table. | Callers misjudge water depth. A mapped zone is a second, independent signal, and it stays explainable as one more driver bar. Camp locations also let Pukaar say where the nearest camp is. |
| **5. Offline and low-bandwidth mode** | Cache the district's map tiles and the gazetteer in the control-room PWA (it already has a service worker), queue dispatch actions while offline and sync them later, and send callbacks by SMS when the voice line is down. | In Michaung, power and mobile networks were down for three to four days. A control room that goes blank when the link drops is not a control room. |
| **6. Evon hosted on-prem for triage** | Host Gnani Evon v3.3 in a state data centre and point the existing adapter at it (`LLM_PROVIDER=evon`, see [`docs/EVON-HOSTING.md`](docs/EVON-HOSTING.md)). | Caller data would not leave the state, and there would be no shared rate limit: one live turn costs about 1,000 Groq tokens, so the free tier fits one live call at a time. |
| **7. More languages and cities** | Add gazetteers with local-script aliases for other flood-prone districts (Kerala, Assam, Bihar), local place names for Hindi and Telugu broadcasts, and guard phrases checked by native speakers. | Prisma's `indic-auto` and Timbre already cover more languages than we tested. The limits today are ours: 42 Chennai localities, and only Tamil aliases. |
| **8. Load testing** | Replay the surge recording at hundreds of concurrent calls against a staging server, measure Gnani concurrency, the store (SQLite today) and the `/ws/control` fan-out, then move the store to Postgres if it is the bottleneck. | A flood is a burst. We have measured single live calls and a 24-caller text surge, not a thousand callers at once. |

---

## Run it

Needs Python 3.12, [uv](https://docs.astral.sh/uv/) and Node 18+. On Windows, use `python -m` (Smart App Control blocks `.exe` launchers such as `pytest.exe`).

```bash
uv sync --all-packages
cd frontend && npm ci && npm run build && cd ..

# No keys needed: a scripted Tanglish caller, tone audio, fake triage
FAKE=1 bash run_backend.sh                 # PowerShell: $env:FAKE="1"; ./run_backend.ps1
# open http://127.0.0.1:8766

# Live: copy .env.example to .env and set GNANI_API_KEY and GROQ_API_KEY
cp .env.example .env
uv run python -m uvicorn pukaar.app:create_app --factory --host 127.0.0.1 --port 8766
```

**Static demo, no backend and no keys** (replays the recorded live run; this is what the live demo link serves):

```bash
cd frontend && npm run build:demo          # writes frontend/dist
python -m http.server 8080 -d dist         # open http://localhost:8080
```

See [`docs/DEPLOY-VERCEL.md`](docs/DEPLOY-VERCEL.md) for Vercel. Run `npm run build` again afterwards so a local backend serves the real app.

- Frontend dev server: `cd frontend && npm run dev` (http://localhost:5192, proxies to 8766).
- Noise drill: `uv run python scripts/run_drill.py --n 6` (spends Gnani credits; TTS is cached).
- Before a demo, delete `cache/pukaar.db`: new calls within 300 m and 3 hours merge into old test incidents (dedup working as designed). Use earphones so Pukaar does not hear itself.
- One-page PDF: `uv run --no-project --with markdown --with pypdf python scripts/make_pitch_pdf.py` regenerates [`PITCH.pdf`](PITCH.pdf) from [`PITCH.md`](PITCH.md) (needs Chrome).

---

## Tests

```bash
uv run python -m pytest -q        # 277 passed
```

- **175 backend tests**: severity rules and dedup (`test_domain`, with thresholds and edge cases in `test_domain_edges`), the store's dedup and KPIs (`test_store`), LLM-outage fallbacks and fake mode (`test_fallbacks`), fact extraction and the reply guard (`test_triage`), the agent's question order, guidance, caller merging, dispatch and callbacks (`test_agent`), SMS, relay and dispatch translation (`test_channels`), the REST and WebSocket API (`test_app`), broadcast and CAP (`test_broadcast`), team matching, capacity, ETA and no double booking (`test_allocate`), the SitRep and hotspot clustering (`test_sitrep_hotspots`), the surge simulator and the noise drill scoring, and the rescuer interpreter (`test_interpreter`: both directions, names and numbers kept, the guard fallback, the speaking lock and barge-in, language validation and the `/ws/interpret` protocol end to end with fakes).
- **102 voice-core tests**: the Gnani protocol and offline clients (Prisma stream and REST, Timbre REST and stream, voice cloning), the request gate and 429 retries, the call session (barge-in, echo guard, reconnects, fallback lines, listen-only agents), turn-based STT, audio and the LLM adapter.

---

## Team and family

Team: Nitya Prakash Pandey · Dilavesh Kanz Nidooli

Part of a three-product entry built on one Gnani voice engine:

| Product | What it does |
|---|---|
| [**Dadi vs Scammers**](https://github.com/nitya-prakash-pandey-2005/dadi-vs-scammers) (flagship) | An AI grandmother answers scam calls, wastes the scammer's time and extracts mule accounts into a complaint. |
| **Pukaar** (this repo) | An overflow disaster helpline that answers in the caller's language and puts every caller on the rescue map. |
| [**Apni Awaaz**](https://github.com/nitya-prakash-pandey-2005/apni-awaaz) | Gives people who lost their voice their own voice back from old voice notes. |

Combined pitch: [dadi-vs-scammers/PITCH.md](https://github.com/nitya-prakash-pandey-2005/dadi-vs-scammers/blob/main/docs/THREE-PRODUCTS.md).

Built for Gnani AI's Great Indian AI Internship Challenge. #GnaniAI #GreatIndianAIInternshipChallenge

---

## Project docs

- [`docs/02-design.md`](docs/02-design.md): design and safety rules
- [`docs/design/wireframe.svg`](docs/design/wireframe.svg): low-fidelity wireframe of both screens and the call flow
- [`docs/brand/`](docs/brand/): logo, wordmark and README banner
- [`docs/test-log.md`](docs/test-log.md): every live test, with latency
- [`docs/drill-results.md`](docs/drill-results.md): full noise drill tables
- [`docs/01-gnani-api-reference.md`](docs/01-gnani-api-reference.md): what we learned about the Gnani APIs
- [`docs/review-cl-2026-11-10.md`](docs/review-cl-2026-11-10.md): final review findings and the live checklist
- [`docs/06-demo-and-post.md`](docs/06-demo-and-post.md): demo script
- [`docs/DEPLOY-VERCEL.md`](docs/DEPLOY-VERCEL.md): the static demo on Vercel and how to refresh its recorded data
- [`docs/EVON-HOSTING.md`](docs/EVON-HOSTING.md): how to host Gnani Evon for the LLM adapter
- [`PITCH.md`](PITCH.md) / [`PITCH.pdf`](PITCH.pdf): one-page pitch
