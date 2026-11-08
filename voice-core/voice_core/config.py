"""Settings loaded from the repo-root .env (environment variables win)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values


def repo_root() -> Path:
    """The repo root: the nearest folder (from cwd upwards) holding a uv workspace pyproject,
    falling back to the folder that contains voice-core/."""
    here = Path.cwd().resolve()
    for folder in [here, *here.parents]:
        py = folder / "pyproject.toml"
        if py.exists() and "[tool.uv.workspace]" in py.read_text(encoding="utf-8", errors="ignore"):
            return folder
    return Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    gnani_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    llm_provider: str = "groq"
    intel_llm_provider: str = "groq"
    evon_base_url: str = ""
    evon_api_key: str = ""
    evon_model: str = "gnani-evon"
    stt_mode: str = "stream"
    sample_rate: int = 8000
    cache_dir: Path = Path("cache")


_ENV_KEYS = {
    "gnani_api_key": "GNANI_API_KEY",
    "groq_api_key": "GROQ_API_KEY",
    "groq_model": "GROQ_MODEL",
    "llm_provider": "LLM_PROVIDER",
    "intel_llm_provider": "INTEL_LLM_PROVIDER",
    "evon_base_url": "EVON_BASE_URL",
    "evon_api_key": "EVON_API_KEY",
    "evon_model": "EVON_MODEL",
    "stt_mode": "STT_MODE",
}


@lru_cache(maxsize=1)
def _cached() -> Settings:
    root = repo_root()
    file_vals = dotenv_values(root / ".env") if (root / ".env").exists() else {}
    kwargs: dict = {}
    defaults = Settings()
    for field, env in _ENV_KEYS.items():
        val = os.environ.get(env) or file_vals.get(env) or getattr(defaults, field)
        kwargs[field] = val.strip() if isinstance(val, str) else val
    kwargs["sample_rate"] = int(os.environ.get("SAMPLE_RATE") or file_vals.get("SAMPLE_RATE") or 8000)
    kwargs["cache_dir"] = root / "cache"
    return Settings(**kwargs)


def get_settings(reload: bool = False) -> Settings:
    if reload:
        _cached.cache_clear()
    return _cached()
