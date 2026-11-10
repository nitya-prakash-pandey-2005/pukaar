# voice-core: the shared voice engine (interface contract)

Used by `dadi-vs-scammers`, `apni-awaaz` and `pukaar`. **Canonical copy lives in `dadi-vs-scammers/voice-core`.** Edit it only there, then run `bash dadi-vs-scammers/scripts/sync-core.sh`.
This file is the contract: names, signatures and behaviour that all three projects rely on. If you change a signature, update this file in the same commit.

All audio inside the engine is **PCM16 little-endian mono**. Default sample rate is **8000 Hz** (phone quality).

## `voice_core.config`
- `Settings` (dataclass): `gnani_api_key`, `groq_api_key`, `groq_model`, `llm_provider` ("groq"|"evon"), `intel_llm_provider` ("groq"|"evon"), `evon_base_url`, `evon_api_key`, `evon_model`, `stt_mode` ("stream"|"turn"), `sample_rate: int = 8000`, `cache_dir: Path` (repo-root `cache/`).
- `get_settings(reload: bool = False) -> Settings`: reads the repo-root `.env`; environment variables override it.

## `voice_core.types`
- `Turn` (dataclass): `speaker: str` (free label, e.g. "scammer", "dadi", "caller", "pukaar", "user"), `text: str`, `t: float` (seconds since the session started), `lang: str | None = None`, `latency_ms: float | None = None`.

## `voice_core.audio`
- `pcm16_to_float(b) -> np.ndarray[float32]`, `float_to_pcm16(x) -> bytes`
- `resample(x, src_hz, dst_hz)`, `telephone_band(x, hz)` (300–3400 Hz), `BandPass(hz)` (the same filter as a callable that keeps its state across frames: use it on streamed audio), `mix_at_snr(signal, noise, snr_db)`, `pink_noise(n, seed=0)`
- `FrameBuffer(frame_bytes=1024)`: `.push(b) -> list[bytes]`, `.flush() -> bytes | None`
- `wav_bytes(pcm16, hz) -> bytes`, `read_wav(b) -> (np.ndarray, hz)`

## `voice_core.gnani` (Gnani AI APIs; host `https://api.vachana.ai`)
- **Request gate (live finding, 8 Nov):** a key allows one short request at a time (a second concurrent one gets `429 RATE_LIMITED`). `tts_rest`, `tts_stream`, `transcribe_rest`, `create_voice_embedding` and `tts_clone_rest` all go through `gate.gnani_slot()` and retry 429/5xx (`gate.RETRY_DELAYS` = 0.5, 1, 2 s). The Prisma streaming socket is not gated. `tts_stream` holds the slot while streaming and retries only before its first chunk. Never wrap these calls in your own parallel `gather`; it is safe but they will queue. `gnani_call(fn, *a)` gates any other Gnani call. Env `GNANI_MAX_CONCURRENT` (default 1) if the quota allows more.
- `SttEvent`: `type` in {"connected","speech_start","processing","transcript","error","closed"}, `text`, `language`, `latency_ms`, `raw`
- `build_stt_headers(api_key, *, language_code, model="prisma-v3.0", sample_rate=8000, fmt="codemix", keyterms=None, vad=None) -> dict` (streaming takes exactly one locale: a list such as `"ta-IN,hi-IN"` becomes `indic-auto` on v3.0, or its first locale on v2.5; keyterms are sent as ASCII-escaped JSON)
- `parse_stt_message(msg: str) -> SttEvent`
- `PrismaStream(api_key, **header_kwargs)`: `connect()`, `send_audio(pcm16)`, `send_pcm_realtime(pcm16, sample_rate)`, `commit()`, `events()` (async iterator; ends with "closed"), `close()`, `.connected`
- `transcribe_rest(api_key, wav, *, language_code="hi-IN,en-IN", model="prisma-v3.0", fmt="codemix", keyterms=None) -> SttEvent`
- `build_tts_body(text, *, voice, model="timbre-v3.0", language="hi-IN", speed=1.0, sample_rate=8000, container="raw") -> dict`
- `tts_rest(api_key, text, **body_kwargs) -> bytes`; `tts_stream(api_key, text, **body_kwargs)` (async iterator of PCM chunks; raises `TtsError` if the socket sends nothing for `RECV_TIMEOUT` = 8 s); `TtsError`
- `strip_audio_tags(text) -> str`; `AUDIO_TAGS` (the 13 Timbre v3.0 tags)
- `create_voice_embedding(api_key, wav: bytes) -> dict` (Gnani voice cloning: returns `{embedding, shape, dtype}`; normalises the two documented response shapes)
- `tts_clone_rest(api_key, text, embedding: dict, *, sample_rate=8000) -> bytes` (model `vachana-vc-v1`)
- `TtsCache(cache_dir)`: `get_or_make(api_key, text, **body_kwargs) -> bytes` caches by a hash of (text, voice, model, language, speed, sample_rate) so we never pay twice for the same audio

## `voice_core.llm`
- `LLM(settings, provider=None, purpose="dialogue"|"intel", *, max_retries=1, first_token_timeout=None, timeout=30.0)`: `complete(messages, *, temperature=0.8, max_tokens=220, json_mode=False) -> str`; `stream(messages, ...)` (async iterator of text deltas); `.provider`, `.model`. `purpose="intel"` uses `settings.intel_llm_provider`. **Realtime dialogue should pass `max_retries=0, first_token_timeout=5.0`**: the SDK otherwise sleeps out a 429 `Retry-After` (minutes of dead air); with a timeout set, `stream()` raises `asyncio.TimeoutError` (and closes the response) when no text delta arrives in time. `LLM.last_status` (class attribute) holds the outcome of the most recent call in the process: `{"ok", "error", "provider", "model", "at"}`.
- `parse_json_loose(text) -> dict`
- `voice_core.testing.FakeLLM(replies: list[str])`, `FakeStt(events: list[SttEvent])`, `fake_tts(text, **kw)` (two 320-byte chunks), for offline tests

## `voice_core.turns`
- `is_meaningful(text) -> bool`, `is_echo(text, recent_agent_lines, threshold=0.6) -> bool` (ignores nukta / chandrabindu spelling variants; checks each given line (pass the last few seconds; at most the last 12 are used), and for 3+ words whether ≥ 80 % of the transcript appears in order in all the given lines joined)
- `split_sentences(buf) -> (list[str], remainder)` (splits on `. ! ? । ॥ …` or a newline)
- `TurnBasedStt(api_key, **kw)`: the same `events()` interface as `PrismaStream`, using an energy VAD plus `transcribe_rest`. This is the fallback when the account allows only one active Gnani request at a time.

## `voice_core.session`: generic realtime voice-agent session
An **Agent** is any object with:
```
user_label: str; agent_label: str              # e.g. "scammer"/"dadi", "caller"/"pukaar"
voice: str; tts_language: str; speed: float     # current Timbre settings (may change after language detection)
stt_language_code: str; keyterms: list[str]
def greeting(self) -> str
def filler_texts(self) -> list[str]
def fallback_texts(self) -> list[str]                                  # OPTIONAL: lines for a failed reply (else filler_texts)
def on_language(self, code: str | None) -> None                       # first meaningful turn: switch persona or language
async def reply_sentences(self, history: list[Turn]) -> AsyncIterator[str]
async def on_user_turn(self, history: list[Turn]) -> dict | None      # background analysis; returns an event to send, e.g. {"type":"intel",...}
                                                                      # coalesced: never two at once; turns that arrive meanwhile get ONE more call with the latest history
async def record(self, turn: Turn) -> None                            # persistence hook
```
`VoiceAgentSession(agent, *, send_json, send_audio, settings, stt_factory=None, tts_fn=None, filler_audio=None, noise=None, rng=None, filler_delay=0.25, reconnect_delays=(0.5, 1, 2, 4, 8), first_sentence_timeout=8.0, hangup_grace=3.0, half_duplex=False, stable_after=10.0)`:
- `start()`, `on_audio(pcm16)`, `set_noise(snr_db | None)`, `hangup() -> {"session_seconds": float}`, `.started_at`
- `filler_audio` (text -> PCM16) is used by reference: an app may fill the same dict in place after the session started (warm-up).
- `half_duplex=True` (speakerphone / laptop speakers; settable as `.half_duplex` before `start()`): `speech_start` never barges in, `processing` is ignored while the agent is busy and for 0.8 s after her audio ends, and only a transcript that is not echo interrupts her. Echo is checked against everything the agent said in the last 8 s (longer while audio is still queued). Default `False` = earphones, full-duplex barge-in.
- `hangup()` stops speech and STT at once, then waits up to `hangup_grace` (default 3 s) for pending `on_user_turn` analysis (its event is still sent) before `agent.end()` and `session_ended`; `session_seconds` excludes that wait.
- Sends JSON events: `session_started`, `turn` {speaker, text, t, lang, latency_ms}, `agent_speaking` {on}, `stop_audio`, `status` {stt: connected|reconnecting|error}, `session_ended`, plus whatever `on_user_turn` returns. Sends binary PCM16 for agent speech.
- Pinned behaviour: barge-in (`speech_start` while speaking → cancel and `stop_audio`; a new transcript while a reply is still streaming or playing also sends `stop_audio` before the new reply, except over a filler clip that this same utterance triggered); a filler after `processing` if no reply audio within 250 ms; ignore non-meaningful and echo transcripts; **no dead air**: when a reply produces no audio (agent error, first sentence later than `first_sentence_timeout`, empty reply, TTS failure) the session plays a pre-rendered line from `fallback_texts()` (else `filler_texts()`), only texts present in `filler_audio`, never the same clip twice in a row, sent as a normal agent `turn` with `"fallback": true`; STT reconnect with backoff 0.5/1/2/4/8 s, then `status: error` and no more attempts; the backoff resets only after a stream stayed up `stable_after` (10 s) or produced a transcript (also when the very first connect in `start()` fails: the greeting still plays and `status: reconnecting` is sent; `start()` never raises for an STT failure); TTS failure → retry once on `timbre-v2.5` with tags stripped; noise (if set) mixed into user audio at `snr_db` after the band-pass (stateful across frames, no clicks).

## `voice-core/web` (browser, plain ES modules)
- `startMic({ targetRate = 8000, onFrame }) -> Promise<{ stop() }>` (AudioWorklet; 512-sample Int16 frames)
- `createPcmPlayer({ sampleRate = 8000 }) -> { play(arrayBuffer), flush(), level() }`
- `pcmToWav(int16Array, sampleRate) -> Blob`, `decodeToPcm16(file: File|Blob, targetRate) -> Promise<Int16Array>` (decodes WhatsApp .opus/.ogg, .mp3 or .wav in the browser)

## Scripts
- `scripts/smoke_gnani.py [--llm]`: live checks (TTS REST, STT REST, TTS stream, STT stream, concurrency, LLM)
- `scripts/eval_llm.py --provider groq|evon`: Groq-vs-Evon evaluation (persona replies in 3 languages, intel JSON, Pukaar triage JSON, Awaaz quick replies); writes `docs/evon-eval.md`
