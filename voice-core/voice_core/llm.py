"""One OpenAI-compatible LLM client for Groq (fast hosted) and Evon v3.3 (self-hosted vLLM/llama.cpp)."""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import AsyncIterator

from openai import AsyncOpenAI

from .config import Settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_THINK_RE = re.compile(r"<think>.*?</think>", re.S)
_FENCE_RE = re.compile(r"```(?:json)?", re.I)


def parse_json_loose(text: str) -> dict:
    """Return the first balanced {...} object in text (ignores <think> blocks and code fences)."""
    t = _FENCE_RE.sub("", _THINK_RE.sub("", text or ""))
    start = t.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(t)):
            ch = t[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(t[start : i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except ValueError:
                        pass
                    break
        start = t.find("{", start + 1)
    raise ValueError("no JSON object found")


class LLM:
    """purpose="dialogue" uses settings.llm_provider; purpose="intel" uses settings.intel_llm_provider.
    Evon silently falls back to Groq when EVON_BASE_URL is not configured.

    Realtime callers should pass max_retries=0 and first_token_timeout (seconds): the SDK otherwise retries a
    429 after its Retry-After (up to minutes of dead air), and stream() raises asyncio.TimeoutError when no text
    arrives in time so the caller can say a fallback line instead."""

    # process-wide outcome of the most recent call, for /api/health: {"ok", "error", "provider", "model", "at"}
    last_status: dict = {}

    def __init__(self, settings: Settings, provider: str | None = None, purpose: str = "dialogue", *,
                 max_retries: int = 1, first_token_timeout: float | None = None, timeout: float = 30.0):
        self.purpose = purpose
        p = provider or (settings.intel_llm_provider if purpose == "intel" else settings.llm_provider)
        if p == "evon" and not settings.evon_base_url:
            p = "groq"
        self.provider = p
        if p == "evon":
            self._base, self._key, self.model = settings.evon_base_url, settings.evon_api_key or "EMPTY", settings.evon_model
            self._extra = {"chat_template_kwargs": {"enable_thinking": False}, "repetition_penalty": 1.1}
        else:
            self._base, self._key, self.model = GROQ_BASE_URL, settings.groq_api_key, settings.groq_model
            self._extra = {}
        self.max_retries = max_retries
        self.first_token_timeout = first_token_timeout
        self.timeout = timeout
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(base_url=self._base, api_key=self._key or "missing", timeout=self.timeout,
                                       max_retries=self.max_retries)
        return self._client

    def _kwargs(self, temperature: float, max_tokens: int, json_mode: bool) -> dict:
        kw: dict = {"model": self.model, "temperature": temperature, "max_tokens": max_tokens}
        if self.provider == "evon":
            kw["top_p"] = 0.95
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        if self._extra:
            kw["extra_body"] = self._extra
        return kw

    def _note(self, error: BaseException | None) -> None:
        # /api/health shows whether the conversation works; a background intel call hitting a rate limit must not
        # turn the status pill into "LLM error" while the caller is being answered normally
        if self.purpose != "dialogue":
            return
        LLM.last_status = {"ok": error is None, "error": None if error is None else repr(error)[:300],
                           "provider": self.provider, "model": self.model, "at": time.time()}

    async def complete(self, messages: list[dict], *, temperature: float = 0.8, max_tokens: int = 220,
                       json_mode: bool = False) -> str:
        try:
            r = await self.client.chat.completions.create(messages=messages,
                                                          **self._kwargs(temperature, max_tokens, json_mode))
        except Exception as e:
            self._note(e)
            raise
        self._note(None)
        return _THINK_RE.sub("", r.choices[0].message.content or "").strip()

    async def stream(self, messages: list[dict], *, temperature: float = 0.8, max_tokens: int = 220) -> AsyncIterator[str]:
        budget = self.first_token_timeout
        loop = asyncio.get_running_loop()
        deadline = loop.time() + budget if budget else None
        create = self.client.chat.completions.create(
            messages=messages, stream=True, **self._kwargs(temperature, max_tokens, False)
        )
        try:
            resp = await (asyncio.wait_for(create, budget) if budget else create)
        except Exception as e:
            self._note(e)
            raise
        it = resp.__aiter__()
        in_think, pending, first = False, "", True
        while True:
            try:
                if deadline is not None:  # until the first text (or <think>) delta arrives
                    chunk = await asyncio.wait_for(it.__anext__(), max(0.001, deadline - loop.time()))
                else:
                    chunk = await it.__anext__()
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError as e:
                self._note(e)
                try:
                    await resp.close()
                except Exception:
                    pass
                raise
            except Exception as e:
                self._note(e)
                raise
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if not delta:
                continue
            deadline = None
            if first:
                first = False
                self._note(None)
            pending += delta
            out = ""
            while pending:
                if in_think:
                    end = pending.find("</think>")
                    if end == -1:
                        pending = pending[-8:]
                        break
                    pending, in_think = pending[end + 8 :], False
                else:
                    st = pending.find("<think>")
                    if st == -1:
                        # keep a short tail in case a tag is split across chunks (max(0, ...): a buffer shorter
                        # than the tag, such as "<thi", must be held back whole, not sliced from the end)
                        safe = max(0, len(pending) - 7) if "<" in pending[-7:] else len(pending)
                        out, pending = out + pending[:safe], pending[safe:]
                        break
                    out, pending, in_think = out + pending[:st], pending[st + 7 :], True
            if out:
                yield out
        if pending and not in_think:
            yield pending
