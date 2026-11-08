# Research and idea selection

Written 8 Nov 2026, with about 2.5 days left before the deadline.

## 1. What actually decides who wins

Reading the rules closely gives five facts that drive every choice:

1. **The internship shortlist is decided by verified public engagement** (reactions, comments, reshares) on your LinkedIn/X demo post, counted at the cutoff. A brilliant project that nobody shares does not reach the interview. **The idea has to be shareable.**
2. **Engagement only counts until 10 Nov, 11:59 PM.** Every hour the post is live earlier is more engagement, so we need a working demo fast and should post by the morning of 10 Nov at the latest.
3. **The awards reward specific things:** code-mixed voice (Hinglish, Tanglish, Benglish), noisy phone audio, creative use of Gnani's models, and the best 60-second video. One project can be a strong candidate for several of them.
4. **The interview decides the offer.** You must be able to explain the architecture, the trade-offs and why each decision was made. Gnani's business is voice agents for banks and contact centres, so a project close to that world gives you a great interview story.
5. **Competition:** participants have already posted ASHA-worker assistants (AshaSathi), emergency handover voice assistants (AyuSwar), legal tools and others. Many will copy the four example ideas on the page. Those spaces are crowded.

## 2. Hard constraints we found

- Gnani speech APIs: Prisma STT (REST, streaming WebSocket, batch), Timbre TTS (REST, SSE, WebSocket), **voice cloning**, and Timbre v3.0 **audio tags** (`<laugh>`, `<sigh>`, `<coughs>`, `<whispers>` and more). Details in `01-gnani-api-reference.md`.
- **Evon has no hosted API.** It needs an A100/H100-class GPU. Your laptop has 16 GB RAM and Intel Iris Xe graphics, so it cannot run Evon. The real-time conversation brain needs a fast hosted LLM, and Evon can be plugged in through an OpenAI-compatible interface if we host it on a cloud GPU.
- Your account may be limited to **one active API request at a time**, so the design must not depend on many parallel calls.
- Demo data must be synthetic: no real phone numbers, account numbers or recorded calls.

## 3. Long list: 18 ideas considered

| # | Idea | Verdict | Why |
|---|---|---|---|
| 1 | Kannada farmer crop/weather helpline | Rejected | Organiser's own example; many duplicates expected |
| 2 | Hinglish kirana phone-order bot | Rejected | Organiser's example; duplicates |
| 3 | Noisy call summariser | Rejected | Organiser's example; low virality |
| 4 | Tamil voice tutor | Rejected | Organiser's example; crowded ed-tech space |
| 5 | AI for 112 emergency calls | Rejected | Bengaluru's "Namma 112" already runs a multilingual AI; a hackathon project (Sankatmochan) and a participant (AyuSwar) already did versions |
| 6 | Disaster-surge helpline with live rescue map ("Pukaar") | **Shortlisted** | Huge impact and a strong fit for noisy audio, but it overlaps with #5 and is complex to build |
| 7 | ASHA health-worker voice assistant | Rejected | Already posted by participants; Microsoft's ASHABot exists |
| 8 | Live phone-call translator between Indian languages | Rejected | Pixel and Samsung phones already do live call translation |
| 9 | Scam-call detector that warns elders | Rejected | Truecaller and Google already ship call scam detection |
| 10 | Gram Sabha meeting minutes | Rejected | The government launched "SabhaSaar" for this in 2025 |
| 11 | Voice job-matching for blue-collar workers | Rejected | Vahan, Apna and WorkIndia exist |
| 12 | Ambient doctor scribe in Indian languages | Rejected | EkaScribe and Augnito exist |
| 13 | Live classroom translator for migrant children (Bihari kids in Kerala schools) | Considered | Real and novel, but the demo looks like "Google Translate with voice" and would get less engagement |
| 14 | Voice-bot QA arena (synthetic Indic callers stress-testing voice agents) | Considered | Gnani would love it, but the public won't share a B2B testing tool |
| 15 | Cyber-fraud "golden hour" complaint helper (1930) | Merged into #17 | Good, but stronger as part of #17 |
| 16 | **"Awaaz": get your own voice back** (voice banking for throat-cancer, stroke and ALS patients in Indian languages) | **Shortlisted** | Deeply emotional; no Indian-language voice-banking app for laryngectomy patients found |
| 17 | **AI scam-baiter "Dadi"** that wastes scammers' time and harvests their mule accounts | **Recommended** | See below |
| 18 | AI radio bulletins for villages | Rejected | Low novelty and low virality |

## 4. The three finalists compared

Scores are out of 5; build risk is scored so that 5 means safest.

| Criterion | **Dadi vs Scammers** | Awaaz (voice back) | Pukaar (disaster line) |
|---|---|---|---|
| Real-world impact | 4 | 5 | 5 |
| Novelty in India | 4 | 4 | 3 |
| Shareability on LinkedIn/X | **5** | 4 | 4 |
| Uses Gnani's strengths (telephony, code-mix, audio tags, cloning) | **5** | 4 | 5 |
| 60-second demo drama | **5** | 4 (needs a real patient to feel authentic) | 5 |
| Build risk in 48 h | 3 | 4 | 2 |
| Award fit | Mixed Vibes, Jugaad Genius, Crowd Favourite, Demo Day Drop, Noise Canceller | Jugaad Genius, Real Deal, Main Character | Noise Canceller, Real Deal |
| Interview story for a BFSI/contact-centre voice-AI company | **5** (fraud is a top bank problem) | 3 | 4 |
| **Total** | **36** | 32 | 32 |

## 5. Recommendation: "Dadi vs Scammers"

**One line:** India's first multilingual AI grandmother who picks up scam calls, keeps fraudsters talking for as long as possible in Hinglish, Tanglish or Benglish, and quietly collects their UPI IDs, bank accounts and scripts for a ready-to-file cybercrime report.

### Why this one (the reasons you can give in the interview)

1. **The problem is huge and current.** Indians lost about **₹22,845 crore to cyber fraud in 2024** (I4C, Ministry of Home Affairs), more than three times the ₹7,465 crore of 2023. 2025 saw about 21 to 28 lakh complaints. "Digital arrest" scams alone took about ₹1,935 crore in 2024, and the Prime Minister addressed them on national radio.
2. **It flips the economics of scamming.** Blocking a scam call costs the scammer nothing; they dial the next number. A bot that keeps them busy for 20 to 40 minutes costs them real time that would otherwise go to a real victim. Every minute with Dadi is a minute a real grandmother is not being scammed.
3. **It turns scam calls into intelligence.** Scammers must eventually share a UPI ID or bank account to get paid. Dadi "tries to pay" and collects those mule accounts, which can be reported and frozen. Police and banks fight scams mainly through mule accounts (the RBI built MuleHunter.AI for this). We get them straight from the scammer's mouth.
4. **It uses Gnani's models in an unexpected way (Jugaad Genius).** Gnani builds voice bots that banks use for collections. We use the same technology against fraudsters. Timbre v3.0 audio tags give Dadi a real personality: she coughs, sighs, laughs and "searches for her glasses". Prisma's code-mix mode handles the scammer's Hinglish, and its training on telephonic audio handles noisy call-centre lines.
5. **It fits Mixed Vibes exactly.** The award names Hinglish, Tanglish and Benglish. We ship three grandmothers: **Dadi** (Hinglish), **Paati** (Tanglish) and **Thakuma** (Benglish).
6. **It is made to be shared.** O2's English "Daisy" (UK, Nov 2024) went viral worldwide and talked to over 1,000 scammers, some for 40 minutes. Nobody has built the Indian, multilingual version. Clips of an Indian grandmother trolling a fake "CBI officer" are exactly the content Indians share, comment on ("I need this for my parents!") and reshare.
7. **A clean business story for Gnani.** "Telecoms already flag scam calls and block them. Route them to Dadi instead." Banks and telecoms are Gnani's customers, so this shows you understand their market.
8. **It is sovereign by design.** Scam-call intelligence is sensitive law-enforcement data. Running on Gnani's Indian stack, with Evon's open weights able to run in a government data centre, keeps the data in India. That is literally the challenge's theme.

### Honest prior art (say this openly; it builds trust)
- **O2 Daisy (UK, 2024):** English only, a marketing campaign, no intelligence output. Our version adds Indian languages and code-mixing, the mule-account and script intelligence, auto-drafted complaints for India's reporting systems (cybercrime.gov.in / 1930 / Sanchar Saathi Chakshu), and an AI-vs-AI arena for testing.
- No Indian-language AI scam-baiter turned up in our searches.

### Risks and how we handle them
| Risk | Mitigation |
|---|---|
| Voice conversation latency (STT, then LLM, then TTS) | Grandma persona hides latency: instant pre-recorded fillers ("Haan beta... ek minute...") play while the LLM thinks. Slowness is in character. |
| LLM refuses to "play along" | The persona is the victim, not the scammer; a careful system prompt plus a fallback model |
| Demo must not be misleading or use real calls | The scammer is played live by a person or by our AI scammer, clearly labelled "simulated scam call" |
| Ethics of deceiving people | Dadi only talks to people who called her number (a honeypot). She never calls anyone, never uses real personal data, and only gives fake details. |
| Evon can't run on the laptop | Real-time brain on a fast hosted LLM; Evon plugged in through the same OpenAI-compatible interface for report writing if we host it on a cloud GPU |

## 6. Runner-up: Awaaz
Pick this if you have a personal story (for example a relative who lost their voice) and a person willing to appear in the video. It is the most emotional idea, but without a real patient it can look staged, and it uses fewer of Gnani's telephony strengths.

## Sources
- Cyber fraud losses 2024: https://telanganatoday.com/indians-lost-a-whopping-rs-22845-crore-to-cyber-fraud-in-2024-govt
- 2025 figures and digital-arrest share: https://theprint.in/india/cybercrime-saw-24-spike-in-2025-indians-lost-rs-22495-crore-mainly-in-investment-scams/2859930/ and https://moneylife.in/article/fraud-alert-india-is-losing-over-22000-crore-a-year-in-cyber-scams-and-the-worst-is-yet-to-come/80612.html
- Digital arrest scam overview: https://en.wikipedia.org/wiki/Digital_arrest_scam
- O2 Daisy: https://news.virginmediao2.co.uk/o2-unveils-daisy-the-ai-granny-wasting-scammers-time/ and https://www.malwarebytes.com/blog/news/2024/11/ai-granny-daisy-takes-up-scammers-time-so-they-cant-bother-you
- Bengaluru Namma 112 AI: https://www.deccanherald.com/amp/story/india/karnataka/bengaluru/bengaluru-police-launch-multilingual-ai-integration-into-112-emergency-response-systems-3984955
- Gnani voice cloning launch: https://www.businesstoday.in/amp/technology/story/gnaniai-launches-zero-shot-voice-cloning-tts-model-for-12-indic-languages-516896-2026-02-19
- Evon model card: https://huggingface.co/gnani/gnani-evon-v3.3-30B-A3B
- Gnani docs: https://docs.gnani.ai/llms.txt
