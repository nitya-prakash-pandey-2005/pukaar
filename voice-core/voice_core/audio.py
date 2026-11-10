"""Audio helpers. Everything is mono; PCM16 is little-endian signed 16-bit."""

from __future__ import annotations

import io
import wave
from functools import lru_cache

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt, sosfilt_zi


def pcm16_to_float(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype="<i2").astype(np.float32) / 32768.0


def float_to_pcm16(x: np.ndarray) -> bytes:
    y = np.clip(np.asarray(x, dtype=np.float32), -1.0, 1.0)
    return (y * 32767.0).astype("<i2").tobytes()


def resample(x: np.ndarray, src_hz: int, dst_hz: int) -> np.ndarray:
    if src_hz == dst_hz:
        return np.asarray(x, dtype=np.float32)
    g = np.gcd(int(src_hz), int(dst_hz))
    return resample_poly(x, dst_hz // g, src_hz // g).astype(np.float32)


@lru_cache(maxsize=8)
def _band_sos(hz: int):
    high = min(3400.0, hz / 2 * 0.95)
    return butter(4, [300.0, high], btype="bandpass", fs=hz, output="sos")


def telephone_band(x: np.ndarray, hz: int) -> np.ndarray:
    """300-3400 Hz band-pass, like a phone line."""
    return sosfilt(_band_sos(int(hz)), np.asarray(x, dtype=np.float32)).astype(np.float32)


class BandPass:
    """telephone_band for a stream of frames: keeps the filter state between calls, so 64 ms browser frames do
    not each restart from silence (that made a click train at the frame rate)."""

    def __init__(self, hz: int):
        self.sos = _band_sos(int(hz))
        self.zi = sosfilt_zi(self.sos) * 0.0

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float32)
        if not len(x):
            return x
        y, self.zi = sosfilt(self.sos, x, zi=self.zi)
        return y.astype(np.float32)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if len(x) else 0.0


def mix_at_snr(signal: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Add noise (tiled or trimmed to the signal length) so that the result has the given SNR."""
    signal = np.asarray(signal, dtype=np.float32)
    if len(signal) == 0 or len(noise) == 0:
        return signal.copy()
    reps = int(np.ceil(len(signal) / len(noise)))
    n = np.tile(np.asarray(noise, dtype=np.float32), reps)[: len(signal)]
    s_rms, n_rms = _rms(signal), _rms(n)
    if s_rms == 0 or n_rms == 0:
        return signal.copy()
    gain = s_rms / (n_rms * 10 ** (snr_db / 20.0))
    return (signal + n * gain).astype(np.float32)


def pink_noise(n: int, seed: int = 0) -> np.ndarray:
    """Approximate 1/f noise via spectral shaping, normalised to RMS 0.1."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    f = np.arange(len(spec))
    f[0] = 1
    spec = spec / np.sqrt(f)
    out = np.fft.irfft(spec, n).astype(np.float32)
    r = _rms(out)
    return out * (0.1 / r) if r else out


class FrameBuffer:
    """Re-chunks arbitrary byte input into fixed-size frames (Prisma needs exactly 1024 bytes)."""

    def __init__(self, frame_bytes: int = 1024):
        self.frame_bytes = frame_bytes
        self._buf = bytearray()

    def push(self, b: bytes) -> list[bytes]:
        self._buf.extend(b)
        out = []
        while len(self._buf) >= self.frame_bytes:
            out.append(bytes(self._buf[: self.frame_bytes]))
            del self._buf[: self.frame_bytes]
        return out

    def flush(self) -> bytes | None:
        if not self._buf:
            return None
        last = bytes(self._buf) + b"\x00" * (self.frame_bytes - len(self._buf))
        self._buf.clear()
        return last


def wav_bytes(pcm16: bytes, hz: int) -> bytes:
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(hz))
        w.writeframes(pcm16)
    return bio.getvalue()


def read_wav(b: bytes) -> tuple[np.ndarray, int]:
    """Reads a PCM WAV (mono or stereo, 16-bit) into float32 mono."""
    with wave.open(io.BytesIO(b), "rb") as w:
        hz, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"only 16-bit WAV supported, got {width * 8}-bit")
    x = pcm16_to_float(raw)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1).astype(np.float32)
    return x, hz
