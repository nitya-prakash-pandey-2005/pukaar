# WP-1: Host Gnani Evon v3.3 as an OpenAI-compatible endpoint

**Owner:** teammate. **Goal:** by Sunday evening, a URL `EVON_BASE_URL` (ending in `/v1`) that answers
`POST /chat/completions` with Evon, protected by an API key, with **reasoning off**, first token in under about 1 s and at least 30 tokens/s.
**Why it matters:** with Evon running we can honestly say "the full Gnani stack: Prisma hears, Evon thinks, Timbre speaks". That is the challenge's "sovereign AI" theme and a strong eligibility and interview point.

Facts (checked on 8 Nov 2026):
- Original weights: `gnani/gnani-evon-v3.3-30B-A3B` (BF16, about 64 GB). Architecture `nemotron_h` (Mamba2-Transformer hybrid MoE, 30B total, about 3.5B active). Needs vLLM 0.12 or newer, or SGLang, on an 80 GB GPU. **No hosted API exists** (no Hugging Face Inference Provider).
- The model card's vLLM command uses the id `gnani/gnani-evon-v3.3` while the repo page is `gnani/gnani-evon-v3.3-30B-A3B`. Use whichever resolves (try the long one first).
- 4-bit GGUF (third party, **gated: needs the maintainer's approval**): `luminenio/gnani-evon-v3.3-30B-A3B-GGUF`. Sizes: Q4_K_M 24.7 GB · Q4_K_S 22.1 GB · IQ4_XS 18.4 GB · Q3_K_M 20.0 GB · Q8_0 33.8 GB. Needs a recent llama.cpp with `nemotron_h_moe` support (latest release is fine).
- Reasoning off: per request `"chat_template_kwargs": {"enable_thinking": false}`. Recommended sampling: temperature 0.6, top_p 0.95, repetition_penalty 1.1.

## Step 0: do these right now (5 minutes; approvals can take hours)
1. Create a Hugging Face account and a **read** token (huggingface.co/settings/tokens).
2. Open https://huggingface.co/gnani/gnani-evon-v3.3-30B-A3B and accept any access conditions.
3. Open https://huggingface.co/luminenio/gnani-evon-v3.3-30B-A3B-GGUF and **request access**.
4. Pick a strong random API key for the endpoint (e.g. `python -c "import secrets;print(secrets.token_urlsafe(24))"`); this becomes `EVON_API_KEY`.

## Step 1: choose a path

| Path | GPU | Cost | Needs | Quality | Setup time |
|---|---|---|---|---|---|
| **A. RunPod or Vast.ai + vLLM (recommended for the demo)** | A100 80 GB or H100 | about $1.2–2.5/hour, only while running | step 0.2 | full BF16 | 30–45 min |
| B. Modal + vLLM | A100-80GB | **$30 free credits/month** (about 12 h of A100) | Modal account | full BF16 | 45–60 min |
| C. RunPod or Vast.ai + llama.cpp | RTX 4090 / A5000 24 GB | about $0.3–0.7/hour | GGUF access (0.3) | 4-bit | 20 min |
| D. Kaggle notebook + llama.cpp + tunnel | 2× T4 (free) | free (weekly GPU quota) | GGUF access, phone-verified Kaggle, **check Kaggle's terms on tunnels/servers first** | 4-bit | 30 min |

Recommendation: start **A** (or **B** to use free credits) today, because demo day needs reliability. Use **C/D** as a cheap development endpoint only if GGUF access arrives.
Always stop paid pods when not testing. A storage volume keeps the weights, so restarts are fast.

## Path A: RunPod (Vast.ai is similar)
1. New pod → GPU **A100 80GB** (or H100) → image `vllm/vllm-openai:latest` (must be vLLM ≥ 0.12) → container disk 30 GB, **volume 120 GB** mounted at `/workspace` → expose HTTP port **8000**.
2. Environment variables: `HF_TOKEN=<your token>`, `HF_HOME=/workspace/hf`, `EVON_API_KEY=<from step 0.4>`.
3. Container start arguments:
```
--model gnani/gnani-evon-v3.3-30B-A3B --served-model-name gnani-evon --trust-remote-code
--max-model-len 16384 --gpu-memory-utilization 0.92 --host 0.0.0.0 --port 8000
--api-key ${EVON_API_KEY} --reasoning-parser nano_v3
```
   - If vLLM rejects `--reasoning-parser nano_v3`, remove it (reasoning stays off per request anyway).
   - If the model id fails, use `gnani/gnani-evon-v3.3`.
   - `--max-model-len 16384` keeps memory low; we never need 128K.
4. The first start downloads about 64 GB (5–15 min). The endpoint is `https://<POD_ID>-8000.proxy.runpod.net/v1`.

## Path B: Modal
Follow Modal's current example **modal.com/docs/examples/vllm_inference** and change only:
- the model: `gnani/gnani-evon-v3.3-30B-A3B` with `--served-model-name gnani-evon --trust-remote-code --max-model-len 16384 --api-key $EVON_API_KEY`; parser `nano_v3` instead of the example's parser, or none;
- the GPU: `"A100-80GB"`;
- secrets: `modal secret create huggingface HF_TOKEN=...` and `modal secret create evon EVON_API_KEY=...`, attached to the function;
- keep a Modal Volume for the Hugging Face cache, `scaledown_window` of about 15 min, and a long startup timeout (20 min for the first download).
Deploy with `modal deploy evon_vllm.py`. Keep that file in `infra/` (it contains no secrets). The endpoint is the URL Modal prints, plus `/v1`.

## Path C/D: llama.cpp + GGUF
1. Download the prebuilt Linux CUDA build from https://github.com/ggml-org/llama.cpp/releases/latest: `llama-<build>-bin-ubuntu-cuda-12.8-x64.tar.gz` **and** `cudart-llama-<build>-bin-ubuntu-cuda-12.8-x64.tar.gz`; extract both into the same folder. Or build: `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75` (T4) then `cmake --build build --config Release -j`.
2. Download the model (on Kaggle use `/tmp`, because `/kaggle/working` is too small):
   `hf download luminenio/gnani-evon-v3.3-30B-A3B-GGUF gnani-evon-v3.3-30B-A3B-Q4_K_M.gguf --local-dir /tmp/models`
3. Serve.
   2× T4 (Kaggle):
   ```
   ./llama-server -m /tmp/models/gnani-evon-v3.3-30B-A3B-Q4_K_M.gguf -ngl 99 -ts 1,1 -c 8192 -np 1 -fa auto \
     --host 0.0.0.0 --port 8080 --alias gnani-evon --api-key "$EVON_API_KEY" \
     --chat-template-kwargs '{"enable_thinking":false}'
   ```
   24 GB GPU: use `gnani-evon-v3.3-30B-A3B-IQ4_XS.gguf` and add `-ncmoe 8`. Raise it until the model loads, then lower it for speed.
   **Always pass `-c`.** The GGUF metadata claims a 1M context, which would exhaust memory.
4. Public URL (Kaggle only; RunPod has its own proxy): `cloudflared tunnel --url http://localhost:8080` prints `https://<random>.trycloudflare.com`. The endpoint is that URL plus `/v1`. The URL changes on every restart, so update `.env` each time.

## Step 2: verify (any path)
```bash
export EVON_BASE_URL=https://.../v1 EVON_API_KEY=...
curl -s $EVON_BASE_URL/models -H "Authorization: Bearer $EVON_API_KEY"
curl -s $EVON_BASE_URL/chat/completions -H "Authorization: Bearer $EVON_API_KEY" -H "Content-Type: application/json" -d '{
 "model":"gnani-evon",
 "messages":[{"role":"system","content":"Respond in the same language and script as the question."},
             {"role":"user","content":"एक दादी की तरह एक लाइन में जवाब दो: बेटा, आप कौन बोल रहे हो?"}],
 "temperature":0.6,"top_p":0.95,"max_tokens":120,
 "chat_template_kwargs":{"enable_thinking":false}}'
```
PASS = a short Hindi answer, no `<think>` text, returned within a few seconds.

## Step 3: plug it in
In `.env` of each repo:
```
EVON_BASE_URL=https://.../v1
EVON_API_KEY=...
EVON_MODEL=gnani-evon
INTEL_LLM_PROVIDER=evon      # intel extraction, reports, Pukaar triage (latency matters less)
LLM_PROVIDER=groq            # live conversation; switch to evon if Step 4 shows it is fast enough
```

## Step 4: evaluation (write the results to `docs/evon-eval.md`)
Run `uv run python voice-core/scripts/eval_llm.py --provider evon` and again with `--provider groq` (the script arrives with the `voice-core` push, about 14:00). It measures:
1. Dadi Hinglish persona replies ×5, Paati Tamil ×3, Thakuma Bengali ×3: time to first token, total time, correct script, stays in character.
2. Scam-intel JSON extraction from code-mixed transcripts ×5: valid JSON rate, UPI and phone found.
3. Pukaar triage JSON from a code-mixed flood call ×5: valid JSON rate, location and people count found.
4. Awaaz quick-reply suggestions (3 options in Hindi) ×3.

**Decision rule:** if Evon's valid-JSON rate is 90% or higher and time to first token is 1.2 s or less → `INTEL_LLM_PROVIDER=evon`. If, in addition, persona replies are good and time to first token is 0.8 s or less → also `LLM_PROVIDER=evon` while recording demos.

## Safety and cost
- Always run with an API key. Never post the endpoint URL publicly.
- Stop pods when idle. On RunPod, "Stop" keeps the volume; "Terminate" deletes it.
- Note the hours used in `docs/evon-eval.md`, so we can say what the demo cost.
