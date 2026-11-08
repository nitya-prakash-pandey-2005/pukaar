# The Great Indian AI Internship Challenge: full brief

Sources: the 7 screenshots you shared, plus the official pages gnani.ai/internship, the registration/terms page and gnani.ai/models (read on 8 Nov 2026).

## 1. The deal

| Item | Detail |
|---|---|
| Organiser | Gnani AI (gnani.ai), a Bengaluru voice-AI company |
| Tagline | "Build Sovereign AI for India. Build on Gnani AI's own models and compete for paid internships." |
| Internships | Up to **100** paid six-month internships starting **1 Jan 2027** |
| Stipend | **Up to ₹1 lakh per month per intern**. This is a ceiling, not a fixed amount. Paid per person, never split between teammates. |
| Awards | **₹5 lakh total = ten awards of ₹50,000**. Decided per category, separate from internship selection. **No one can win more than one award.** |
| Eligibility | Enrolled students in India, aged 18+. Solo or team of two. One entry per person or team. |
| Deadline | **10 Nov 2026, 11:59 PM IST**. Final, no extensions. You can edit project details until you press final submit. |
| Build window | 1 Oct to 10 Nov 2026 (41 days) |
| After close | Review, then individual interviews (both teammates interviewed separately) |

## 2. The ten awards (₹50,000 each)

| # | Award | What wins it |
|---|---|---|
| 01 | Main Character | Best build in a regional or low-resource Indian language |
| 02 | Mixed Vibes | Best **code-mixed voice** experience: Hinglish, Tanglish, Benglish |
| 03 | Real Deal | Most useful real-world problem solved (farmers, kirana stores, rural health workers) |
| 04 | Noise Canceller | Performs best on messy, noisy, real telephonic audio |
| 05 | Two-Person Army | Best project by a team of two |
| 06 | Solo Ninja | Best project by one participant |
| 07 | Jugaad Genius | Most **creative or unexpected use** of Gnani AI's models |
| 08 | Small Town, Big Build | Best entry from a college or city in a Tier 2 or Tier 3 town |
| 09 | Demo Day Drop | Best **60-second demo video** |
| 10 | Crowd Favourite | Public votes on LinkedIn and X using #GreatIndianAIInternshipChallenge and #GnaniAI |

Purchased votes, bots and engagement exchanges don't count towards any award.

## 3. Organiser's example ideas (ideas, not requirements)

- Kannada voice helpline reading crop and weather advisories to farmers (Main Character, Real Deal)
- Hinglish voice assistant taking phone orders for a kirana store (Mixed Vibes, Real Deal)
- Call summariser that holds up on noisy phone audio, tested on synthetic calls (Noise Canceller)
- Tamil voice tutor that quizzes students aloud and explains answers (Jugaad Genius)

**Strategic note:** many participants will build exactly these four. Avoid them to stand out.

## 4. Models you can build on

The terms say the **available models are Prisma (STT), Timbre (TTS, beta) and Evon (LLM on Hugging Face)**.

| Model | What it is | Key published claims |
|---|---|---|
| **Prisma** (v2.5, v3.0 released 22 Oct 2026) | Speech-to-text | 14M+ hours of telephonic audio; streams in under 200 ms; 10 Indian languages plus Hinglish, Tanglish and Benglish; #1 on Kathbath Noisy 8 kHz in 8 of 9 languages; handles code-switching and accents; built-in recognition of PAN, Aadhaar and account numbers |
| **Timbre** (v2.5, v3.0) | Text-to-speech (beta) | 10+ Indian languages; context-aware prosody; Indian names, numerals, lakh/crore cadence; streams over WebSocket and SSE; v3.0 adds **audio tags** (laugh, sigh, cough, whisper and more) |
| **Gnani voice cloning** (`vachana-vc-v1`) | Zero-shot voice cloning TTS | Launched Feb 2026 for 12 Indic languages; clone from 5 to 30 seconds of clean speech |
| **Evon v3.3** | Reasoning LLM, open weights | 30B mixture-of-experts (about 3.5B active), Mamba2-Transformer hybrid, 128K context, 11 Indian languages, Apache 2.0. **Not on the API platform.** Self-host only (needs an A100/H100-class GPU). |
| Warp v2.0 | Native speech-to-speech, 5B | **Not in the challenge's list of available models.** Don't depend on it. |

Gnani calls its full stack "Artha, the sovereign stack". The FAQ says the challenge covers the API platform at app.gnani.ai/voice only, not their agent builder.

## 5. The six rules that matter most

1. **Offers and stipends are individual.** Teammates are interviewed separately; one can get an offer without the other.
2. **The brief is open.** No set problem statement. Build any working application on Gnani AI's models or APIs.
3. **Your project uses Gnani AI technology.** The submission names the Gnani models/APIs used and each member's contribution.
4. **You demo it in public.** Post a public **video of the app working** on LinkedIn and/or X. Explain what you built, name the Gnani tech, **tag Gnani AI's official account** (x.com/GnaniAi, linkedin.com/company/gnani-ai), include **#GnaniAI** and **#GreatIndianAIInternshipChallenge**. Nominate one post per platform. **The post must be live before you submit.**
5. **The deadline is fixed:** 11:59 PM IST, 10 Nov 2026.
6. **Keep it authentic.** No bought engagement, bots, paid promotion, engagement swaps, plagiarism or misleading demos. Substantiated breaches can disqualify.

Data rule: "Don't put anyone's real phone numbers, account numbers, Aadhaar, PAN or recorded calls into your project or demo. Use synthetic data."

## 6. How people get selected

1. **Engagement check:** Gnani verifies reactions, comments and reshares on your nominated posts, counted at the closing cutoff.
2. **Eligibility check:** genuine use of Gnani AI technology, and the participation rules are met.
3. **Shortlisting:** "The eligible projects with the strongest verified engagement are shortlisted for interview."
4. **Interviews:** one to one, individual.
5. **Written offers:** based on assessed skills, interview performance and fit for available roles.

**Strategic consequence:** the internship shortlist is driven by **public engagement on your post**. That makes the demo video and the post as important as the code. Engagement only counts until the cutoff, so **post as early as possible**.

## 7. What to submit

- Step 2, Build: project title; the problem you are solving; who will use it; the Gnani models/APIs used; each member's contribution.
- Step 4, Submit: demo video; written project explanation; Gnani models/APIs used; one nominated post link per platform.
- The submission form arrives by **email** after registration.
- No repo field or demo length limit was found. The 60-second length matters only for the Demo Day Drop award, but a tight 60 to 90 second video is best for engagement anyway.

## 8. Resources

- 5,000 programme credits per registration (the primary registrant gets them for a team); keys are created at **app.gnani.ai/voice**
- Docs: docs.gnani.ai (index at docs.gnani.ai/llms.txt)
- Discord support: discord.gg/aECcvtABpq
- Evon weights: huggingface.co/gnani/gnani-evon-v3.3-30B-A3B

## 9. Small print

- An internship is confirmed only by a written offer after the interview stage.
- Gnani may modify, suspend or cancel any part of the contest.
- Open questions to ask on Discord if needed: are other LLMs allowed alongside Gnani models (nothing forbids them; Gnani's own Pipecat example pairs Gnani speech with a Groq LLM), and what do the credits cover?
