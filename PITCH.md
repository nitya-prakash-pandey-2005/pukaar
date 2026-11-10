# Pukaar · पुकार · புகார்: when every line is busy, Pukaar picks up

**Team:** Nitya Prakash Pandey & Dilavesh Kanz Nidooli · Built on Gnani **Prisma v3.0** (speech-to-text) and **Timbre v3.0** (text-to-speech) · **Live demo:** [pukaar-snowy.vercel.app](https://pukaar-snowy.vercel.app/) · **Video:** [Google Drive](https://drive.google.com/drive/folders/1byHuJr_KoofV7NTVx1sCutXupmnX0D_S?usp=sharing) · Code: [github.com/nitya-prakash-pandey-2005/pukaar](https://github.com/nitya-prakash-pandey-2005/pukaar)

## Problem

In a flood, everyone calls at once and a helpline has a fixed number of people.

- **Chennai, Cyclone Michaung (Dec 2023):** "almost every call to the complaint cell went unanswered till December 7" ([DT Next](https://www.dtnext.in/news/city/calls-to-govt-helplines-go-unanswered-754073)).
- **Kerala floods (Aug 2018):** 483 people died and 14.50 lakh were in relief camps ([IANS](https://morungexpress.com/483-dead-flood-loss-more-keralas-annual-outlay-vijayan)). Volunteers built keralarescue.in, which received over 1 crore aid and rescue requests ([ThePrint](https://theprint.in/governance/behind-official-kerala-rescue-website-are-1500-techies-working-for-free/102568)).

## Product

An overflow emergency line that answers when no human can.

- **It talks.** It calms the caller in Tamil, Tanglish, Hindi, Telugu or English and asks one question at a time, in the order a rescue team needs: where, how many, anyone hurt, how deep is the water, anyone vulnerable.
- **It is safe by design.** It gives only instructions from 16 approved entries. A guard blocks "you are safe" and any arrival time until a dispatcher confirms an ETA.
- **It triages in a way you can audit.** The LLM only extracts facts; a fixed rule table scores severity and shows every point.
- **It builds one map.** It locates callers from spoken landmarks and merges duplicate callers into one incident on a control-room map. SMS works too, and a missed-call mode needs no balance.
- **Humans stay in charge, with help.** For each incident it ranks the best rescue team with plain reasons (boat, distance, ETA, capacity); a human confirms every dispatch and the caller hears it in their own language. A plan covers the whole queue, hotspots show where calls cluster, and a one-page district SitRep prints.
- **It interprets.** A live voice interpreter lets a Hindi- or English-speaking rescue team talk to a Tamil or Telugu caller (Prisma both ways, Timbre speaks), under the same guard.
- **It broadcasts.** One English alert is spoken in 7 languages and exported as CAP 1.2, the standard India's SACHET alert platform is built on.

## Proof (live on Gnani's servers, 10 Nov 2026, synthetic callers)

- **Live calls:** Prisma wrote a Tamil caller's words in Tamil script with the meaning intact. Severity rose to high mid-call and to **critical 90** as facts arrived. Three calls merged into one rooftop incident. LLM time to the first reply sentence averaged 0.72–1.05 s.
- **8 Nov live call:** Prisma took 90–133 ms per transcript.
- **Noise drill** (6 synthetic calls per noise level, 8 kHz, rain down to 0 dB): triage accuracy was the same as on clean audio, and Tamil transcripts stayed at 3–7% character error.
- **Live interpreter:** rescuer (Hindi) → caller (Tamil) in 2.3 s and back in 1.6 s, from releasing the button to translated speech.
- **Tests:** 277 automated tests pass; CI is green on GitHub.

## How it is different

Bengaluru's Namma 112 "VANKI" (2026) translates for human call-takers. Telangana's AI-ERSS (2026) filters duplicates and ranks severity for them. To our knowledge, as of November 2026, no public deployment has an AI voice agent that itself answers overflow disaster calls in code-mixed Tamil, Hindi and English, triages with explainable rules, guards against false reassurance and emits CAP 1.2 alerts.

## Honesty notes

- All callers, the surge and the drill are synthetic. The phone location is simulated.
- The live demo is a static replay of the real run above, so it spends no API credits. For live calls, run the repo with your own keys.
- The dialogue runs on Groq (`qwen/qwen3.8-27b`). Gnani Evon v3.3 fits the same adapter, but there is no hosted API for it.
- The drill sample is small.

## One engine, three products

Pukaar shares its realtime voice engine with [Dadi vs Scammers](https://github.com/nitya-prakash-pandey-2005/dadi-vs-scammers) and [Apni Awaaz](https://github.com/nitya-prakash-pandey-2005/apni-awaaz). The engine handles barge-in, fillers, an echo guard, reconnects and a gate for Gnani's one-request-per-key limit. See the [combined pitch](https://github.com/nitya-prakash-pandey-2005/pukaar/blob/main/docs/THREE-PRODUCTS.pdf).

#GnaniAI #GreatIndianAIInternshipChallenge
