from voice_core.config import get_settings
from voice_core.types import Turn


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY", "k1")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("INTEL_LLM_PROVIDER", "evon")
    s = get_settings(reload=True)
    assert s.gnani_api_key == "k1"
    assert s.llm_provider == "groq" and s.intel_llm_provider == "evon"
    assert s.sample_rate == 8000
    assert s.cache_dir.name == "cache"


def test_turn_defaults():
    t = Turn("scammer", "hello", 1.5)
    assert t.lang is None and t.latency_ms is None
