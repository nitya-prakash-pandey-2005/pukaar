import numpy as np

from voice_core.audio import (
    FrameBuffer,
    float_to_pcm16,
    mix_at_snr,
    pcm16_to_float,
    pink_noise,
    read_wav,
    resample,
    telephone_band,
    wav_bytes,
)


def test_framebuffer_emits_exact_1024_byte_frames():
    fb = FrameBuffer(1024)
    assert fb.push(b"\x00" * 1000) == []
    frames = fb.push(b"\x01" * 1100)  # 2100 bytes total -> 2 frames, 52 left
    assert [len(f) for f in frames] == [1024, 1024]
    last = fb.flush()
    assert last is not None and len(last) == 1024
    assert fb.flush() is None


def test_mix_at_snr_hits_target_ratio():
    sig = (np.sin(np.linspace(0, 2000, 8000)) * 0.5).astype(np.float32)
    noise = pink_noise(3000, seed=1)
    mixed = mix_at_snr(sig, noise, 10.0)
    n = mixed - sig
    snr = 20 * np.log10(np.sqrt(np.mean(sig**2)) / np.sqrt(np.mean(n**2)))
    assert abs(snr - 10.0) < 0.2 and len(mixed) == len(sig)


def test_pcm_roundtrip_and_resample_length():
    x = np.linspace(-0.9, 0.9, 1600).astype(np.float32)
    assert np.allclose(pcm16_to_float(float_to_pcm16(x)), x, atol=1e-4)
    assert len(resample(x, 16000, 8000)) == 800


def test_float_to_pcm16_clips():
    out = pcm16_to_float(float_to_pcm16(np.array([2.0, -2.0], dtype=np.float32)))
    assert out.max() <= 1.0 and out.min() >= -1.0


def test_wav_roundtrip():
    pcm = float_to_pcm16(np.zeros(800, dtype=np.float32))
    data, hz = read_wav(wav_bytes(pcm, 8000))
    assert hz == 8000 and len(data) == 800


def test_telephone_band_removes_low_hum():
    t = np.arange(8000) / 8000
    hum = np.sin(2 * np.pi * 50 * t).astype(np.float32)
    out = telephone_band(hum, 8000)
    assert np.sqrt(np.mean(out[2000:] ** 2)) < 0.05


def test_band_pass_keeps_state_across_frames():
    import numpy as np

    from voice_core.audio import BandPass, telephone_band

    sr = 8000
    t = np.arange(sr * 2) / sr
    x = (0.1 * np.sin(2 * np.pi * 440 * t) + 0.05 * np.sin(2 * np.pi * 1700 * t)).astype(np.float32)
    whole = telephone_band(x, sr)
    bp = BandPass(sr)
    framed = np.concatenate([bp(x[i:i + 512]) for i in range(0, len(x), 512)])
    assert np.max(np.abs(framed - whole)) < 1e-4


def test_session_noise_path_has_no_frame_clicks():
    import numpy as np

    from voice_core.audio import float_to_pcm16, pcm16_to_float, telephone_band
    from voice_core.config import Settings
    from voice_core.session import VoiceAgentSession

    sr = 8000
    t = np.arange(sr) / sr
    x = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    sess = VoiceAgentSession(object(), send_json=None, send_audio=None, settings=Settings(sample_rate=sr))
    sess.snr_db = 20.0
    out = np.concatenate([pcm16_to_float(sess._add_noise(float_to_pcm16(x[i:i + 512]))) for i in range(0, len(x), 512)])
    ref = telephone_band(pcm16_to_float(float_to_pcm16(x)), sr)
    assert np.max(np.abs(out - ref)) < 1e-3
