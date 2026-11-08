"""Generic realtime voice-agent session: user audio -> Prisma STT -> Agent -> Timbre TTS -> user.

Handles: barge-in, in-character filler clips while the agent "thinks", echo/silence guards,
STT reconnect with backoff (train-grade networks), TTS fallback, and optional noise injection
(to demonstrate Prisma on messy calls). See voice-core/README.md for the Agent protocol.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Awaitable, Callable

import numpy as np

from .audio import float_to_pcm16, pcm16_to_float, telephone_band
from .config import Settings
from .gnani.stt_stream import PrismaStream, SttEvent
from .gnani.tts import strip_audio_tags, tts_stream
from .turns import TurnBasedStt, is_echo, is_meaningful
from .types import Turn

log = logging.getLogger(__name__)
SendJson = Callable[[dict], Awaitable[None]]
SendAudio = Callable[[bytes], Awaitable[None]]
NOISE_REF_RMS = 0.08  # typical speech RMS used to set a constant noise floor


def default_stt_factory(settings: Settings, agent) -> Any:
    kw = dict(language_code=agent.stt_language_code, sample_rate=settings.sample_rate,
              keyterms=getattr(agent, "keyterms", None))
    if settings.stt_mode == "turn":
        return TurnBasedStt(settings.gnani_api_key, **kw)
    return PrismaStream(settings.gnani_api_key, vad={"x-min-silence-ms": "450"}, **kw)


class VoiceAgentSession:
    def __init__(
        self,
        agent,
        *,
        send_json: SendJson,
        send_audio: SendAudio,
        settings: Settings,
        stt_factory: Callable[[], Any] | None = None,
        tts_fn: Callable[..., Any] | None = None,
        filler_audio: dict[str, bytes] | None = None,
        noise: np.ndarray | None = None,
        rng: random.Random | None = None,
        filler_delay: float = 0.25,
        reconnect_delays: tuple[float, ...] = (0.5, 1, 2, 4, 8),
    ):
        self.agent = agent
        self.send_json = send_json
        self.send_audio = send_audio
        self.settings = settings
        self.sr = settings.sample_rate
        self.stt_factory = stt_factory or (lambda: default_stt_factory(settings, agent))
        self.tts_fn = tts_fn or tts_stream
        self.filler_audio = filler_audio or {}
        self.noise = noise
        self.snr_db: float | None = None
        self.rng = rng or random.Random()
        self.filler_delay = filler_delay
        self.reconnect_delays = reconnect_delays

        self.history: list[Turn] = []
        self.started_at = 0.0
        self._t0 = 0.0
        self._stt = None
        self._stt_task: asyncio.Task | None = None
        self._speak_task: asyncio.Task | None = None
        self._filler_task: asyncio.Task | None = None
        self._analysis_lock = asyncio.Lock()
        self._bg: set[asyncio.Task] = set()
        self._recent_agent_lines: list[str] = []
        self._speaking_until = 0.0
        self._reply_audio_started = False
        self._last_filler: str | None = None
        self._lang_set = False
        self._closing = False
        self._noise_pos = 0

    # ------------------------------------------------------------------ lifecycle
    def now(self) -> float:
        return time.monotonic() - self._t0

    async def start(self) -> None:
        self._t0 = time.monotonic()
        self.started_at = time.time()
        info = self.agent.session_info() if hasattr(self.agent, "session_info") else {}
        await self.send_json({"type": "session_started", "started_at": self.started_at, **info})
        greeting = self.agent.greeting()
        if greeting:
            self._recent_agent_lines.append(greeting)
        await self._open_stt()
        if greeting:
            self._speak_task = asyncio.create_task(self._speak_fixed(greeting))

    async def hangup(self) -> dict:
        self._closing = True
        for t in [self._speak_task, self._filler_task, self._stt_task, *self._bg]:
            if t and not t.done():
                t.cancel()
        if self._stt is not None:
            try:
                await self._stt.close()
            except Exception:
                pass
        secs = self.now()
        if hasattr(self.agent, "end"):
            try:
                self.agent.end(secs)
            except Exception as e:
                log.warning("agent.end failed: %r", e)
        await self._safe_json({"type": "session_ended", "session_seconds": secs})
        return {"session_seconds": secs}

    async def wait_idle(self, timeout: float = 3.0) -> None:
        """For tests: wait until speaking, analysis and pending background work are done."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            busy = [t for t in [self._speak_task, self._filler_task, *self._bg] if t and not t.done()]
            if not busy and not self._analysis_lock.locked():
                await asyncio.sleep(0.02)
                busy = [t for t in [self._speak_task, self._filler_task, *self._bg] if t and not t.done()]
                if not busy:
                    return
            await asyncio.sleep(0.01)

    # ------------------------------------------------------------------ audio in
    async def set_noise(self, snr_db: float | None) -> None:
        self.snr_db = snr_db

    def _add_noise(self, pcm16: bytes) -> bytes:
        x = telephone_band(pcm16_to_float(pcm16), self.sr)
        if self.noise is None or not len(self.noise) or not len(x):
            return float_to_pcm16(x)
        n = len(x)
        idx = (np.arange(n) + self._noise_pos) % len(self.noise)
        self._noise_pos = (self._noise_pos + n) % len(self.noise)
        seg = self.noise[idx]
        n_rms = float(np.sqrt(np.mean(self.noise**2))) or 1.0
        gain = NOISE_REF_RMS / (n_rms * 10 ** (self.snr_db / 20.0))
        return float_to_pcm16(x + seg * gain)

    async def on_audio(self, pcm16: bytes) -> None:
        if self._closing or self._stt is None or not getattr(self._stt, "connected", False):
            return
        if self.snr_db is not None:
            pcm16 = self._add_noise(pcm16)
        try:
            await self._stt.send_audio(pcm16)
        except Exception as e:  # socket died; the STT loop will notice and reconnect
            log.info("send_audio failed: %r", e)

    # ------------------------------------------------------------------ STT
    async def _open_stt(self) -> None:
        stt = self.stt_factory()
        await stt.connect()
        self._stt = stt
        self._stt_task = asyncio.create_task(self._stt_loop(stt))

    async def _stt_loop(self, stt) -> None:
        try:
            async for ev in stt.events():
                if ev.type == "closed":
                    break
                await self._on_stt_event(ev)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("stt loop error: %r", e)
        if not self._closing:
            await self._reconnect()

    async def _reconnect(self) -> None:
        await self._safe_json({"type": "status", "stt": "reconnecting"})
        for delay in self.reconnect_delays:
            await asyncio.sleep(delay)
            if self._closing:
                return
            try:
                await self._open_stt()
                await self._safe_json({"type": "status", "stt": "connected"})
                return
            except Exception as e:
                log.info("reconnect failed: %r", e)
        await self._safe_json({"type": "status", "stt": "error", "message": "speech recognition unavailable"})

    async def _on_stt_event(self, ev: SttEvent) -> None:
        if ev.type == "connected":
            await self._safe_json({"type": "status", "stt": "connected"})
        elif ev.type == "speech_start":
            if self._agent_busy():
                await self._barge_in()
        elif ev.type == "processing":
            if not self._agent_busy():
                self._schedule_filler()
        elif ev.type == "transcript":
            await self._on_transcript(ev)
        elif ev.type == "error":
            log.info("stt error event: %s", ev.raw)

    def _agent_busy(self) -> bool:
        return (self._speak_task is not None and not self._speak_task.done()) or time.monotonic() < self._speaking_until

    async def _barge_in(self) -> None:
        for t in (self._speak_task, self._filler_task):
            if t and not t.done():
                t.cancel()
        self._speaking_until = 0.0
        await self._safe_json({"type": "stop_audio"})
        await self._safe_json({"type": "agent_speaking", "on": False})

    async def _on_transcript(self, ev: SttEvent) -> None:
        text = ev.text
        if not is_meaningful(text) or is_echo(text, self._recent_agent_lines):
            return
        if not self._lang_set:
            self._lang_set = True
            evt = self.agent.on_language(ev.language)
            if isinstance(evt, dict):
                await self._safe_json(evt)
        turn = Turn(self.agent.user_label, text, round(self.now(), 2), ev.language, ev.latency_ms)
        self.history.append(turn)
        await self._record(turn)
        await self._safe_json({"type": "turn", "speaker": turn.speaker, "text": text, "t": turn.t,
                               "lang": turn.lang, "latency_ms": turn.latency_ms})
        # a new user turn supersedes anything still being said
        if self._speak_task and not self._speak_task.done():
            self._speak_task.cancel()
        self._reply_audio_started = False
        self._speak_task = asyncio.create_task(self._reply())
        self._spawn(self._analyse())

    # ------------------------------------------------------------------ speaking
    def _schedule_filler(self) -> None:
        if self._filler_task and not self._filler_task.done():
            return
        self._reply_audio_started = False
        self._filler_task = asyncio.create_task(self._filler_after_delay())

    async def _filler_after_delay(self) -> None:
        await asyncio.sleep(self.filler_delay)
        if self._reply_audio_started:
            return
        options = [t for t in self.agent.filler_texts() if t in self.filler_audio and t != self._last_filler]
        if not options:
            return
        text = self.rng.choice(options)
        self._last_filler = text
        self._recent_agent_lines.append(text)
        await self._emit_audio(self.filler_audio[text])

    async def _emit_audio(self, chunk: bytes) -> None:
        now = time.monotonic()
        self._speaking_until = max(self._speaking_until, now) + len(chunk) / 2 / self.sr
        await self.send_audio(chunk)

    async def _tts(self, sentence: str):
        kw = dict(voice=self.agent.voice, language=self.agent.tts_language, speed=self.agent.speed, sample_rate=self.sr)
        try:
            async for chunk in self.tts_fn(self.settings.gnani_api_key, sentence, **kw):
                yield chunk
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("TTS failed (%r); retrying on timbre-v2.5", e)
        try:
            kw.update(model="timbre-v2.5", voice="Poorvi", language="hi-en" if self.agent.tts_language == "hi-IN" else self.agent.tts_language)
            async for chunk in self.tts_fn(self.settings.gnani_api_key, strip_audio_tags(sentence), **kw):
                yield chunk
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("TTS fallback failed: %r", e)

    async def _cached_or_tts(self, text: str):
        if text in self.filler_audio:  # pre-rendered (greeting, fillers): instant and free
            audio = self.filler_audio[text]
            step = max(2, (self.sr // 5) * 2)  # 200 ms chunks
            for i in range(0, len(audio), step):
                yield audio[i : i + step]
            return
        async for chunk in self._tts(text):
            yield chunk

    async def _speak_fixed(self, text: str) -> None:
        spoken = False
        try:
            async for chunk in self._cached_or_tts(text):
                if not spoken:
                    spoken = True
                    await self._safe_json({"type": "agent_speaking", "on": True})
                await self._emit_audio(chunk)
        finally:
            turn = Turn(self.agent.agent_label, text, round(self.now(), 2))
            self.history.append(turn)
            await self._record(turn)
            await self._safe_json({"type": "turn", "speaker": turn.speaker, "text": text, "t": turn.t})
            await self._finish_speaking()

    async def _reply(self) -> None:
        said: list[str] = []
        try:
            async for sentence in self.agent.reply_sentences(list(self.history)):
                said.append(sentence)
                self._recent_agent_lines.append(sentence)
                async for chunk in self._tts(sentence):
                    if not self._reply_audio_started:
                        self._reply_audio_started = True
                        if self._filler_task and not self._filler_task.done():
                            self._filler_task.cancel()
                        await self._safe_json({"type": "agent_speaking", "on": True})
                    await self._emit_audio(chunk)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("reply failed: %r", e)
        finally:
            if said:
                text = " ".join(said)
                turn = Turn(self.agent.agent_label, text, round(self.now(), 2))
                self.history.append(turn)
                await self._record(turn)
                meta = self.agent.turn_meta() if hasattr(self.agent, "turn_meta") else {}
                await self._safe_json({"type": "turn", "speaker": turn.speaker, "text": text, "t": turn.t, **meta})
            await self._finish_speaking()

    async def _finish_speaking(self) -> None:
        await self._safe_json({"type": "agent_speaking", "on": False})

    # ------------------------------------------------------------------ analysis + utils
    async def _analyse(self) -> None:
        async with self._analysis_lock:
            try:
                evt = await self.agent.on_user_turn(list(self.history))
            except Exception as e:
                log.warning("analysis failed: %r", e)
                return
            if isinstance(evt, dict):
                await self._safe_json(evt)

    def _spawn(self, coro) -> None:
        t = asyncio.create_task(coro)
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)

    async def _record(self, turn: Turn) -> None:
        try:
            await self.agent.record(turn)
        except Exception as e:
            log.warning("record failed: %r", e)

    async def _safe_json(self, msg: dict) -> None:
        try:
            await self.send_json(msg)
        except Exception as e:
            log.info("send_json failed: %r", e)
