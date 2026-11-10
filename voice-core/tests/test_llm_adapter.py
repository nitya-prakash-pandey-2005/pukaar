"""LLM adapter details the realtime path depends on: <think> blocks stripped from streams even when the tags are split
across chunks, Dadi's sound tags kept, Evon request options, loose JSON parsing and health status on errors.
No network: the OpenAI client is replaced by a fake."""

import pytest

from voice_core.config import Settings
from voice_core.llm import LLM, parse_json_loose


def _settings(**kw):
    base = dict(groq_api_key="g", groq_model="qwen/test", evon_base_url="http://evon.local/v1", evon_model="evon")
    return Settings(**{**base, **kw})


class _Chunk:
    def __init__(self, text, empty=False):
        self.choices = [] if empty else [type("C", (), {"delta": type("D", (), {"content": text})()})()]


class _Stream:
    def __init__(self, items, fail_after=None):
        self.items, self.fail_after = items, fail_after

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for i, x in enumerate(self.items):
            if self.fail_after is not None and i == self.fail_after:
                raise RuntimeError("connection reset")
            yield x if isinstance(x, _Chunk) else _Chunk(x)

    async def close(self):
        pass


def _client(create):
    completions = type("Co", (), {"create": staticmethod(create)})()
    return type("Cl", (), {"chat": type("Ch", (), {"completions": completions})()})()


def _streaming(items, fail_after=None):
    async def create(**kw):
        return _Stream(items, fail_after)

    return _client(create)


async def _text(llm):
    return "".join([c async for c in llm.stream([{"role": "user", "content": "hi"}])])


@pytest.mark.parametrize("chunks, expected", [
    (["<think>plan</think>Haan beta."], "Haan beta."),
    (["<thi", "nk>reasoning ", "more</th", "ink>Haan ", "beta."], "Haan beta."),  # tags split across chunks
    (["Haan <", "coughs> ruko."], "Haan <coughs> ruko."),  # Dadi's sound tags survive
    (["Pehle ", "<think>x</think>", "phir."], "Pehle phir."),
    (["<think>never closes"], ""),
    ([_Chunk("", empty=True), "", "ok."], "ok."),  # keep-alive chunks without choices or text
])
async def test_stream_strips_think_blocks(chunks, expected):
    llm = LLM(_settings())
    llm._client = _streaming(chunks)
    assert await _text(llm) == expected


async def test_stream_error_after_first_token_is_raised_and_noted(monkeypatch):
    monkeypatch.setattr(LLM, "last_status", {})
    llm = LLM(_settings())
    llm._client = _streaming(["Haan ", "beta"], fail_after=1)
    got = []
    with pytest.raises(RuntimeError):
        async for c in llm.stream([]):
            got.append(c)
    assert got == ["Haan "] and LLM.last_status["ok"] is False and "connection reset" in LLM.last_status["error"]


async def test_complete_strips_think_and_records_health(monkeypatch):
    monkeypatch.setattr(LLM, "last_status", {})
    seen = {}

    async def create(**kw):
        seen.update(kw)
        msg = type("M", (), {"content": "<think>hmm</think> {\"a\": 1} "})()
        return type("R", (), {"choices": [type("Ch", (), {"message": msg})()]})()

    llm = LLM(_settings())
    llm._client = _client(create)
    assert await llm.complete([], json_mode=True, max_tokens=50) == '{"a": 1}'
    assert seen["response_format"] == {"type": "json_object"} and seen["max_tokens"] == 50
    assert seen["model"] == "qwen/test" and "extra_body" not in seen and "top_p" not in seen
    assert LLM.last_status["ok"] is True and LLM.last_status["provider"] == "groq"


async def test_complete_failure_is_raised_and_noted(monkeypatch):
    monkeypatch.setattr(LLM, "last_status", {})

    async def create(**kw):
        raise RuntimeError("Error code: 429 rate_limit_exceeded")

    llm = LLM(_settings())
    llm._client = _client(create)
    with pytest.raises(RuntimeError):
        await llm.complete([])
    assert LLM.last_status["ok"] is False and "429" in LLM.last_status["error"]


def test_evon_request_options():
    llm = LLM(_settings(), provider="evon")
    assert llm.provider == "evon" and llm.model == "evon" and llm._key == "EMPTY"
    kw = llm._kwargs(0.5, 100, False)
    assert kw["top_p"] == 0.95 and "response_format" not in kw
    assert kw["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}, "repetition_penalty": 1.1}


def test_parse_json_loose_edge_cases():
    # braces and escaped quotes inside strings do not confuse the scanner
    assert parse_json_loose('note {"q": "he said \\"pay {now}\\"", "n": 2} end') == {"q": 'he said "pay {now}"', "n": 2}
    # a broken object is skipped and the next valid one is returned
    assert parse_json_loose("{not json} then {\"ok\": true}") == {"ok": True}
    with pytest.raises(ValueError):
        parse_json_loose("no braces here")
    with pytest.raises(ValueError):
        parse_json_loose("")
