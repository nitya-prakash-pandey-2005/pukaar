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
