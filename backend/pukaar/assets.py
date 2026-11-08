"""Pre-rendered greeting and fillers (Timbre, cached on disk) and synthetic rain noise for the caller line."""

from __future__ import annotations

import logging

import numpy as np
from voice_core.config import Settings
from voice_core.gnani import TtsCache

from .agent import CALLBACK_GREETING, FILLERS, GREETING, PukaarAgent

log = logging.getLogger(__name__)


def filler_jobs() -> list[tuple[str, str]]:
    """(text, Timbre language) for the greeting and every filler."""
    return [(GREETING, "ta-IN"), (CALLBACK_GREETING, "ta-IN")] + [(t, f"{lang}-IN") for lang, texts in FILLERS.items() for t in texts]


async def load_or_make_fillers(settings: Settings) -> dict[str, bytes]:
    """text -> PCM16 at settings.sample_rate. Renders once, then free from cache. Never raises."""
    cache = TtsCache(settings.cache_dir)
    out: dict[str, bytes] = {}
    for text, lang in filler_jobs():
        kw = dict(voice=PukaarAgent.voice, language=lang, speed=PukaarAgent.speed, sample_rate=settings.sample_rate)
        hit = cache.get(cache.key(text, **kw))
        if hit is None and settings.gnani_api_key:
            try:
                hit = await cache.get_or_make(settings.gnani_api_key, text, **kw)
            except Exception as e:
                log.warning("filler render failed (%s): %r", text[:20], e)
        if hit:
            out[text] = hit
    return out


def rain_noise(seconds: float, hz: int = 8000, seed: int = 0) -> np.ndarray:
    """Heavy rain: brown-ish rumble plus random droplet clicks, normalised to peak 0.9."""
    rng = np.random.default_rng(seed)
    n = int(seconds * hz)
    rumble = np.cumsum(rng.standard_normal(n))
    rumble -= np.convolve(rumble, np.ones(64) / 64, mode="same")  # remove drift, keep the low roar
    drops = np.zeros(n)
    idx = rng.integers(0, n, size=int(seconds * 400))
    drops[idx] = rng.uniform(-1, 1, size=idx.size)
    drops = np.convolve(drops, np.exp(-np.arange(24) / 4), mode="same")  # short decaying clicks
    x = rumble / (np.abs(rumble).max() + 1e-9) + 0.6 * drops / (np.abs(drops).max() + 1e-9)
    return (0.9 * x / (np.abs(x).max() + 1e-9)).astype(np.float32)
