"""One OpenAI-compatible LLM client for Groq (fast hosted) and Evon v3.3 (self-hosted vLLM/llama.cpp)."""

from __future__ import annotations

import json
import re
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
    Evon silently falls back to Groq when EVON_BASE_URL is not configured."""

    def __init__(self, settings: Settings, provider: str | None = None, purpose: str = "dialogue"):
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
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(base_url=self._base, api_key=self._key or "missing", timeout=30.0, max_retries=1)
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

    async def complete(self, messages: list[dict], *, temperature: float = 0.8, max_tokens: int = 220,
                       json_mode: bool = False) -> str:
        r = await self.client.chat.completions.create(messages=messages, **self._kwargs(temperature, max_tokens, json_mode))
        return _THINK_RE.sub("", r.choices[0].message.content or "").strip()

    async def stream(self, messages: list[dict], *, temperature: float = 0.8, max_tokens: int = 220) -> AsyncIterator[str]:
        resp = await self.client.chat.completions.create(
            messages=messages, stream=True, **self._kwargs(temperature, max_tokens, False)
        )
        in_think, pending = False, ""
        async for chunk in resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if not delta:
                continue
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
                        # keep a short tail in case a tag is split across chunks
                        safe = len(pending) - 7 if "<" in pending[-7:] else len(pending)
                        out, pending = out + pending[:safe], pending[safe:]
                        break
                    out, pending, in_think = out + pending[:st], pending[st + 7 :], True
            if out:
                yield out
        if pending and not in_think:
            yield pending
