import numpy as np
from voice_core.config import Settings

from pukaar.agent import FILLERS, GREETING
from pukaar.assets import filler_jobs, load_or_make_fillers, rain_noise


def test_rain_noise_is_finite_and_audible():
    x = rain_noise(2.0, 8000, seed=1)
    rms = float(np.sqrt(np.mean(x ** 2)))
    assert x.shape == (16000,) and np.isfinite(x).all() and 0.05 < rms < 1.0
    assert np.array_equal(x, rain_noise(2.0, 8000, seed=1))


def test_filler_jobs_use_each_fillers_language():
    jobs = filler_jobs()
    assert (GREETING, "ta-IN") in jobs and (FILLERS["hi"][0], "hi-IN") in jobs and (FILLERS["en"][0], "en-IN") in jobs


async def test_fillers_without_key_returns_empty(tmp_path):
    assert await load_or_make_fillers(Settings(cache_dir=tmp_path)) == {}
