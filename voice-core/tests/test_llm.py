import pytest

from voice_core.config import Settings
from voice_core.llm import LLM, parse_json_loose
from voice_core.testing import FakeLLM


def test_parse_json_loose_handles_fences_and_think():
    assert parse_json_loose('<think>x</think>```json\n{"a": 1, "b": {"c": 2}}\n```') == {"a": 1, "b": {"c": 2}}
    assert parse_json_loose('Sure! {"s": "a } brace"} trailing') == {"s": "a } brace"}
    with pytest.raises(ValueError):
        parse_json_loose("no json here")


def _settings(**kw):
    base = dict(groq_api_key="g", llm_provider="groq", intel_llm_provider="evon", groq_model="m",
                evon_base_url="http://x/v1", evon_api_key="k", evon_model="e")
    base.update(kw)
    return Settings(**base)


def test_provider_selection():
    s = _settings()
    assert LLM(s).model == "m" and LLM(s).provider == "groq"
    assert LLM(s, provider="evon").model == "e"
    assert LLM(s, purpose="intel").provider == "evon"


def test_evon_falls_back_to_groq_when_unconfigured():
    s = _settings(evon_base_url="")
    assert LLM(s, purpose="intel").provider == "groq"


async def test_fake_llm_stream_and_complete():
    f = FakeLLM(["हाँ बेटा, बोलो।", "second"])
    assert "".join([c async for c in f.stream([])]) == "हाँ बेटा, बोलो।"
    assert await f.complete([]) == "second"
    assert await f.complete([]) == ""  # exhausted -> empty


class _Chunk:
    def __init__(self, text):
        self.choices = [type("C", (), {"delta": type("D", (), {"content": text})()})()]


class _SlowStream:
    def __init__(self, first_delay, texts):
        self.first_delay, self.texts, self.closed = first_delay, list(texts), False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        import asyncio

        yield _Chunk("")  # role-only chunk arrives at once
        await asyncio.sleep(self.first_delay)
        for t in self.texts:
            yield _Chunk(t)

    async def close(self):
        self.closed = True


def _fake_client(stream):
    async def create(**kw):
        return stream

    completions = type("Co", (), {"create": staticmethod(create)})()
    return type("Cl", (), {"chat": type("Ch", (), {"completions": completions})()})()


async def test_stream_first_token_timeout_raises_and_closes():
    import asyncio

    s = _SlowStream(1.0, ["late"])
    llm = LLM(_settings(), first_token_timeout=0.05)
    llm._client = _fake_client(s)
    with pytest.raises(asyncio.TimeoutError):
        [c async for c in llm.stream([])]
    assert s.closed


async def test_stream_without_timeout_waits_and_later_tokens_are_not_limited():
    s = _SlowStream(0.1, ["haan ", "beta."])
    llm = LLM(_settings(), first_token_timeout=0.5)
    llm._client = _fake_client(s)
    assert "".join([c async for c in llm.stream([])]) == "haan beta."


def test_max_retries_is_configurable():
    s = _settings()
    assert LLM(s, max_retries=0).client.max_retries == 0
    assert LLM(s).client.max_retries == 1


async def test_last_status_records_failures_and_successes(monkeypatch):
    monkeypatch.setattr(LLM, "last_status", {})

    async def boom(**kw):
        raise RuntimeError("Error code: 404 model_not_found")

    llm = LLM(_settings())
    llm._client = type("Cl", (), {"chat": type("Ch", (), {"completions": type("Co", (), {"create": staticmethod(boom)})()})()})()
    with pytest.raises(RuntimeError):
        [c async for c in llm.stream([])]
    assert LLM.last_status["ok"] is False and "404" in LLM.last_status["error"]
    llm._client = _fake_client(_SlowStream(0.0, ["ok."]))
    assert "".join([c async for c in llm.stream([])]) == "ok."
    assert LLM.last_status["ok"] is True


def test_only_the_dialogue_llm_sets_the_health_status():
    from voice_core.config import Settings
    from voice_core.llm import LLM

    LLM.last_status = {}
    LLM(Settings(groq_api_key="k"), purpose="intel")._note(RuntimeError("429 rate limit"))
    assert LLM.last_status == {}  # a background intel rate limit must not show "LLM error"
    LLM(Settings(groq_api_key="k"), purpose="dialogue")._note(RuntimeError("404"))
    assert LLM.last_status["ok"] is False
    LLM.last_status = {}
