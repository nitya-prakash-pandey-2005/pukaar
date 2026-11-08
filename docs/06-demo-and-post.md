# Demo video, posts and submission kit (Pukaar)

Replace every `[…]` with **real numbers from your recording**. The rules forbid misleading demos: every number must be true, and every screen already says "Simulated emergency call: synthetic data".

## 1. Recording setup
1. `rm -f cache/pukaar.db` (old test incidents would merge into new calls).
2. `bash run_backend.sh`, then open http://127.0.0.1:8766 and wait for the green "Gnani live" pill (fillers rendered).
3. OBS or Game Bar: 1920×1080, 30 fps, desktop audio + mic. **Earphones on** so Pukaar does not hear itself.
4. The caller (you or a friend) speaks Tamil or Tanglish. Ideas: "Velachery la irukom, veedu full ah thanni…", "naalu peru, maadi mela irukom", "paati ku insulin podanum", "thanni nenju varaikkum vandhuduchu". Hindi works too (a migrant worker).
5. Record 3 full calls; pick the best. Cutting for length is fine (caption "edited for length"); reordering events is not.
6. Groq free tier = 8k tokens/min: do not click "Simulate surge" with `fresh` during a live call. The default surge replays a recording and uses no tokens.

## 2. The 60-second cut (Demo Day Drop award)
| Time | Picture | Sound / caption |
|---|---|---|
| 0–4 s | Black, white text: "During the Chennai floods, people couldn't get through to helplines." | Heavy rain |
| 4–10 s | Caller phone → "Call Pukaar". Pukaar answers in Tamil at once | "பதட்டப்படாதீங்க, நான் உதவறேன்…" |
| 10–30 s | Live call, burnt-in English subtitles. The pin appears on the map, then turns red as facts arrive (people, insulin, chest-deep water). Open the incident: severity drivers | Real call audio |
| 30–38 s | Click "Simulate surge": the map fills with [24] callers in 4 languages; pins merge ("3 callers") | Caption: "Five calls about one rooftop = one incident" |
| 38–46 s | Dispatcher picks "NDRF Boat 2", ETA 25 min → the caller hears it in Tamil | Caption: "The AI never dispatches. A human confirms every boat." |
| 46–54 s | Noise drill card | Caption: "Rain as loud as the voice (0 dB): still [X]% of locations right" |
| 54–60 s | End card: "Pukaar: every call answered, in your language." · "Built on Gnani AI Prisma + Timbre" · #GnaniAI #GreatIndianAIInternshipChallenge | — |

Optional shot (Main Character): "Broadcast alert" card → one English flood alert → play it in Tamil, Hindi and Telugu.

Optional jugaad shot (Jugaad Genius): "No balance? Give a missed call" → the pin appears → the phone rings → Pukaar calls back in Tamil.

## 3. LinkedIn post (native video; tag `@Gnani AI`)
```
When Chennai flooded, helplines were jammed exactly when people needed them most.

So we built Pukaar (पुकार, "a cry for help"): an AI disaster helpline that answers every call, in the caller's own language, while a small control room sees everyone on a live rescue map.

🎙️ A frightened caller speaks Tamil, Tanglish, Hindi or Telugu. Pukaar keeps them calm and asks one question at a time.
🗺️ Every caller becomes a pin. Severity comes from a transparent rule table, not the AI's opinion. Five calls about one rooftop merge into one incident.
🛟 Safety advice comes only from an approved list. The AI never dispatches and never promises a time: a human confirms every boat, and the caller hears it back in their language.
📵 No balance? Give a missed call, and Pukaar calls you back.
🌧️ We tested it with synthetic calls buried in rain on an 8 kHz phone line: at [5] dB, [X]% of locations were still right.

Built on @Gnani AI's voice stack:
• Prisma v3.0: real-time speech-to-text for noisy, code-mixed phone audio
• Timbre v3.0: natural Tamil, Hindi, Telugu and English voices

(All calls in the video are simulated with synthetic data.)

#GnaniAI #GreatIndianAIInternshipChallenge #DisasterResponse #VoiceAI #Chennai
```

## 4. X post (≤ 280 characters; attach the video)
```
Floods jam helplines when people need them most. Pukaar answers every call in Tamil, Hindi or Telugu, triages it and puts the caller on a live rescue map. A human confirms every boat.
Built on @GnaniAi Prisma + Timbre.
#GnaniAI #GreatIndianAIInternshipChallenge
```

## 5. Submission form answers (only if Pukaar is the team's entry; paste and edit)
- **Project title:** Pukaar: an AI disaster helpline that answers every call
- **Problem:** During floods and cyclones (Chennai 2015 and 2023, Kerala 2018, Wayanad 2024), helplines are overwhelmed exactly when calls matter most. Callers give up; control rooms work from spreadsheets.
- **Who will use it:** district emergency operation centres (1077) and state disaster cells as an overflow layer; NDRF/SDRF and volunteer boat teams; callers in any Indian language.
- **Gnani models / APIs used:** Prisma v3.0 realtime STT over WebSocket (`indic-auto`, codemix, disaster keyterms, 8 kHz telephony), Prisma v3.0 REST STT (noise drill), Timbre v3.0 streaming TTS (voice Chetana; dispatch callbacks; pre-rendered fillers).
- **Written explanation (about 150 words):** Pukaar is a realtime voice agent for disaster surges. The caller's 8 kHz audio streams to Gnani Prisma v3.0, which transcribes noisy, code-mixed speech and detects the language. After each turn an LLM extracts structured facts (location, people, water level, injuries, vulnerable people); a transparent rule table scores severity, a gazetteer and the phone's location put the caller on the map, and duplicate reports merge into one incident. The reply asks for the single most important missing fact and may add one instruction from an approved list; a guard blocks invented advice and unconfirmed arrival times. Gnani Timbre v3.0 speaks it in the caller's language, with pre-rendered fillers hiding latency. A dispatcher confirms every rescue, and the caller hears the confirmation in their language, by callback if they hung up. A noise drill measures accuracy on synthetic calls in rain at 0–20 dB.
