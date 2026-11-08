# Gnani API reference (developer cheat-sheet)

Read from docs.gnani.ai on 8 Nov 2026. Full docs index: https://docs.gnani.ai/llms.txt

## Auth and hosts

- Speech APIs base: `https://api.vachana.ai` (WebSocket: `wss://api.vachana.ai/...`). Ignore `api.gnani.ai` (marketing pages only).
- Header: `X-API-Key-ID: <API_KEY>` on REST/SSE; `x-api-key-id` on WebSocket handshakes.
- Keys: created at https://app.gnani.ai/voice. SDKs read env var `GNANI_API_KEY`.
- Errors: 401 bad/missing key, 402 out of credits, 403 scope, **429 "Only 1 active request is allowed at a time"** (concurrency may be 1 on our account, so design for one call at a time), 5xx retry with backoff.
- Browsers cannot set custom WebSocket headers, so **audio must be proxied through our backend**.

## Prisma speech-to-text

### REST (clips up to 30 s)
`POST https://api.vachana.ai/stt/v3` (multipart/form-data)
- `audio_file` (wav/mp3/ogg/flac/aac/m4a, 0.1 to 30 s)
- `model`: `prisma-v3.0` (opt-in) or omit for v2.5
- `language_code`: `hi-IN`, `en-IN`, `bn-IN`, `ta-IN`, `te-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `gu-IN`, `pa-IN`; on v3.0 also `indic-auto` or 1 to 4 comma-separated hints such as `hi-IN,en-IN`
- `format`: `verbatim` | `transcribe` | `codemix` (v3.0: keeps English words in Latin script) | `transliterate` (v3.0: all-Latin output)
- v3.0 context hints: `keyterms` (up to 200), `topic` (up to 1600 chars), `previous_text`, `speaker_names`
- `enable_substitution` + `substitution_map` (find-and-replace rules)
- Response: `{success, request_id, transcript, model, detected_language_code (v3.0), processing_time, end_to_end_latency}`

### Realtime WebSocket
`wss://api.vachana.ai/stt/v3/stream`
- Handshake headers: `x-api-key-id`, `language_code` (or `indic-auto` / list on v3.0), `model: prisma-v3.0`, `x-sample-rate` (8000/16000/44100/48000), `format`, `keyterms`, `topic`, VAD tuning (`x-vad-threshold` 0.7, `x-min-silence-ms` 500, `x-min-speech-ms`, `x-min-segment-ms`, `x-max-speech-s`), `x-idle-timeout-sec`.
- Audio in: **binary frames of raw PCM s16le mono, exactly 1024 bytes (512 samples) per frame**, sent at real-time cadence (32 ms per frame at 16 kHz, 64 ms at 8 kHz).
- Client JSON: `{"type":"commit"}` force-closes the utterance; `{"type":"update_settings", ...}`.
- Server JSON: `connected`, `speech_start`, `processing`, `transcript` (`text`, `is_final: true`, `segment_index`, `latency`, `detected_language_code`), `error`. **Final transcripts only, no interim partials.** Server-side VAD splits utterances.
- Session cap: 15 minutes; then close 1001.

### Batch (long files, diarization, denoise)
`POST /stt/v3/batch/jobs` → `POST /stt/v3/batch/jobs/{id}/start` → poll `GET /stt/v3/batch/jobs/{id}` → `GET .../files` → download `transcript_url`.
Config: `model`, `language_code`, `with_diarization`, `num_speakers`, `with_denoise`, v3.0 `format`/`keyterms`/`topic`. Gives segment timestamps and speaker ids.

## Timbre text-to-speech

- REST: `POST https://api.vachana.ai/api/v1/tts/inference` → raw audio bytes
- SSE: `POST https://api.vachana.ai/api/v1/tts/sse` → events `start`, `chunk` (`audio` base64), `complete`
- WebSocket: `wss://api.vachana.ai/api/v1/tts` → send one JSON request; receive `start`, `audio` (`data.audio` base64), `complete`, `error`

Body:
```json
{
  "text": "...",
  "model": "timbre-v3.0",
  "voice": "Shivani",
  "language": "hi-IN",
  "speed": 1.0,
  "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                   "encoding": "linear_pcm", "container": "wav"}
}
```
- `language`: `auto`, the 10 locales above, or `hi-en` (Hinglish)
- `speed`: 0.85 to 1.15
- containers: `wav`, `raw`, `mp3` (+`bitrate`), `ogg`, `mulaw`/`alaw` (force 8 kHz, telephony)

### Voices
- **timbre-v3.0** (13 voices, every voice speaks all 10 languages, supports audio tags). Female: Shivani, Lakshmi, Kalpana, Chetana, Vasudha, Riyaa, Tarika. Male: Avinash, Prakash, Harshad, Devansh, Shubham, Yashraj.
- **timbre-v2.5** (42 voices with a preferred language). Hinglish: **Poorvi**. Hindi: Nalini, Bhavna, Yashvi, Urmila, Jwala, Chitra, Ambuja, Deepak, Roopesh, Vikrant, Hemraj, Jalaj, Omkar. Tamil: Asmita, Trisha, Brinda, Vedika, Noopur. Bengali: Kirra, Dhruva. English-IN: Kaveri, Trupti, Devika, Pranav, Shlok, Girish. Plus Telugu, Kannada, Malayalam, Marathi, Gujarati and Punjabi voices.

### Audio tags (timbre-v3.0 only)
Inline, case-sensitive, no closing tag: `<laugh>` `<giggle>` `<sigh>` `<exhales>` `<sniffles>` `<yawns>` `<coughs>` `<clears throat>` `<whispers>` `<shouting>` `<excited>` `<slow>` `<pauses>`. Tags count as billable characters.

### Voice cloning
1. `POST https://api.vachana.ai/api/v1/tts/voice-clone/embeddings` (multipart `audio_file`, 5 to 30 s clean speech) → embedding `{embedding, shape [1,768], dtype}`
2. Synthesize with `"model": "vachana-vc-v1"` and `"speaker_embedding": {...}` on REST, SSE or WebSocket.

## Python SDK
`pip install gnani-vachana` (import `gnani`): `GnaniSTTClient`, `GnaniSTTStreamClient`, `GnaniSTTBatchClient`, `GnaniTTSClient`, `GnaniTTSStreamClient`, `GnaniTTSRealtimeClient`. The SDK still defaults to the retired timbre-v2.0, so **always pass `model=` explicitly**.

## Evon v3.3 (LLM)
- Repo `gnani/gnani-evon-v3.3-30B-A3B` (Apache 2.0, nemotron_h architecture). **No hosted inference provider.** Self-host with vLLM/SGLang on an 80 GB GPU; it exposes an OpenAI-compatible `/v1/chat/completions` endpoint.
- Disable thinking: `chat_template_kwargs: {"enable_thinking": false}`. Recommended: temperature 0.6, top_p 0.95, repetition_penalty 1.1.
- Our laptop (16 GB RAM, Iris Xe, no CUDA) **cannot** run it. Options: Kaggle/Colab/Modal GPU with a tunnel, or plug it in later through the same OpenAI-compatible interface.
