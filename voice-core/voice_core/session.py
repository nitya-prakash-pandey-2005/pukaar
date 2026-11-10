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

from .audio import BandPass, float_to_pcm16, pcm16_to_float
from .config import Settings
from .gnani.stt_stream import PrismaStream, SttEvent
from .gnani.tts import strip_audio_tags, tts_stream
from .turns import TurnBasedStt, is_echo, is_meaningful
from .types import Turn

log = logging.getLogger(__name__)
SendJson = Callable[[dict], Awaitable[None]]
SendAudio = Callable[[bytes], Awaitable[None]]
NOISE_REF_RMS = 0.08  # typical speech RMS used to set a constant noise floor
ECHO_WINDOW_S = 8.0  # transcripts are compared with what the agent said in the last 8 s (plus audio still queued)
ECHO_TAIL_S = 0.8  # half duplex: the agent's voice can still reach the mic this long after playback ends


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
        first_sentence_timeout: float | None = 8.0,
        hangup_grace: float = 3.0,
        half_duplex: bool = False,
        stable_after: float = 10.0,
    ):
        self.agent = agent
        self.send_json = send_json
        self.send_audio = send_audio
        self.settings = settings
        self.sr = settings.sample_rate
        self.stt_factory = stt_factory or (lambda: default_stt_factory(settings, agent))
        self.tts_fn = tts_fn or tts_stream
        self.filler_audio = filler_audio if filler_audio is not None else {}  # keep the caller's dict: it may fill later
        self.noise = noise
        self.snr_db: float | None = None
        self.rng = rng or random.Random()
        self.filler_delay = filler_delay
        self.reconnect_delays = reconnect_delays
        self.first_sentence_timeout = first_sentence_timeout
        self.hangup_grace = hangup_grace
        # speakerphone: the mic hears the agent, so only a non-echo transcript may interrupt her (no speech_start
        # barge-in) and VAD events during her speech and its echo tail are ignored
        self.half_duplex = half_duplex
        # an agent that only listens (Guardian) and speaks when it has something to say: no fillers, no fallback line,
        # no barge-in (its warnings are never cut off by the caller; they queue instead)
        self.listen_only = bool(getattr(agent, "listen_only", False))
        self.stable_after = stable_after  # a stream that lived this long (or gave a transcript) resets the backoff
        self._reconnect_attempt = 0

        self.history: list[Turn] = []
        self.started_at = 0.0
        self._t0 = 0.0
        self._stt = None
        self._stt_task: asyncio.Task | None = None
        self._speak_task: asyncio.Task | None = None
        self._filler_task: asyncio.Task | None = None
        self._analysis_lock = asyncio.Lock()
        self._analysis_task: asyncio.Task | None = None
        self._analysis_dirty = False
        self._bg: set[asyncio.Task] = set()
        self._recent_agent_lines: list[str] = []
        self._said_at: list[tuple[float, str]] = []  # (monotonic time, text) of the agent's recent lines
        self._speaking_until = 0.0
        self._reply_audio_started = False
        self._last_filler: str | None = None
        self._last_audio_kind = ""  # "filler" or "speech": what is playing at the caller's end
        self._lang_set = False
        self._closing = False
        self._noise_pos = 0
        self._band = BandPass(self.sr)  # stateful across frames

    # ------------------------------------------------------------------ lifecycle
    def now(self) -> float:
        return time.monotonic() - self._t0

    async def start(self) -> None:
        self._t0 = time.monotonic()
        self.started_at = time.time()
        info = self.agent.session_info() if hasattr(self.agent, "session_info") else {}
        await self.send_json({"type": "session_started", "started_at": self.started_at, **info})
        greeting = self.agent.greeting()
        if greeting:  # starts at once, even before (or without) STT
            self._said(greeting)
            self._speak_task = asyncio.create_task(self._speak_fixed(greeting))
        try:
            await self._open_stt()
        except Exception as e:  # train tunnel, 429, timeout: keep the call alive and keep trying
            log.warning("STT connect failed at start: %r", e)
            self._stt_task = asyncio.create_task(self._reconnect())

    async def hangup(self) -> dict:
        self._closing = True
        secs = self.now()
        for t in [self._speak_task, self._filler_task, self._stt_task]:
            if t and not t.done():
                t.cancel()
        if self._stt is not None:
            try:
                await self._stt.close()
            except Exception:
                pass
        # the last turn often carries the UPI ID: let pending analysis finish (briefly) before ending the call
        pending = [t for t in self._bg if not t.done()]
        if pending and self.hangup_grace > 0:
            await asyncio.wait(pending, timeout=self.hangup_grace)
        for t in list(self._bg):
            if not t.done():
                t.cancel()
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
        x = self._band(pcm16_to_float(pcm16))
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
        opened, heard = time.monotonic(), False
        try:
            async for ev in stt.events():
                if ev.type == "closed":
                    break
                heard = heard or ev.type == "transcript"
                await self._on_stt_event(ev)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("stt loop error: %r", e)
        # only a stream that really worked resets the backoff: a server that accepts and closes at once must not
        # cause a reconnect every 0.5 s forever
        if heard or time.monotonic() - opened >= self.stable_after:
            self._reconnect_attempt = 0
        if not self._closing:
            await self._reconnect()

    async def _reconnect(self) -> None:
        await self._safe_json({"type": "status", "stt": "reconnecting"})
        while self._reconnect_attempt < len(self.reconnect_delays):
            delay = self.reconnect_delays[self._reconnect_attempt]
            self._reconnect_attempt += 1
            await asyncio.sleep(delay)
            if self._closing:
                return
            try:
                await self._open_stt()
                await self._safe_json({"type": "status", "stt": "connected"})
                return
            except Exception as e:
                log.info("reconnect failed: %r", e)
        log.warning("STT gave up after %d reconnect attempts", len(self.reconnect_delays))
        await self._safe_json({"type": "status", "stt": "error", "message": "speech recognition unavailable"})

    def _said(self, text: str) -> None:
        self._recent_agent_lines.append(text)
        del self._recent_agent_lines[:-50]
        now = time.monotonic()
        self._said_at.append((now, text))
        horizon = now - ECHO_WINDOW_S - 60.0
        while self._said_at and self._said_at[0][0] < horizon:
            self._said_at.pop(0)

    def _echo_lines(self) -> list[str]:
        """The agent's lines that may still come back through the mic: the last 8 s (longer while audio is queued),
        and always at least the last two lines."""
        now = time.monotonic()
        since = now - ECHO_WINDOW_S - max(0.0, self._speaking_until - now)
        lines = [t for ts, t in self._said_at if ts >= since]
        return lines if len(lines) >= 2 else self._recent_agent_lines[-2:]

    def _in_echo_tail(self) -> bool:
        return self._agent_busy() or time.monotonic() < self._speaking_until + ECHO_TAIL_S

    async def _on_stt_event(self, ev: SttEvent) -> None:
        if ev.type == "connected":
            await self._safe_json({"type": "status", "stt": "connected"})
        elif ev.type == "speech_start":
            if self.half_duplex or self.listen_only:
                return  # on a speakerphone this is usually her own voice; a real transcript barges in instead
            if self._agent_busy():
                await self._barge_in()
        elif ev.type == "processing":
            if self.listen_only or (self.half_duplex and self._in_echo_tail()):
                return
            if not self._agent_busy():
                self._schedule_filler()
        elif ev.type == "transcript":
            await self._on_transcript(ev)
        elif ev.type == "error":
            log.info("stt error event: %s", ev.raw)

    @property
    def speaking(self) -> bool:
        """True while the agent's audio is (estimated to be) playing at the caller's end. A bridge can use it to keep
        the agent's own voice, echoed back through a speakerphone, out of anything it collects from the caller."""
        return time.monotonic() < self._speaking_until

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
        if not is_meaningful(text) or is_echo(text, self._echo_lines()):
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
        if self.listen_only:  # never cut off a warning: the next reply waits for the one being spoken
            prev = self._speak_task if self._speak_task and not self._speak_task.done() else None
            self._speak_task = asyncio.create_task(self._reply(after=prev))
            self._request_analysis()
            return
        # a new user turn supersedes anything still being said: also flush the old reply's audio already buffered
        # at the caller's end (a filler started by this same utterance may finish; the reply queues behind it)
        if (self._speak_task and not self._speak_task.done()) or (
                time.monotonic() < self._speaking_until and self._last_audio_kind != "filler"):
            await self._barge_in()
        self._reply_audio_started = False
        self._speak_task = asyncio.create_task(self._reply())
        self._request_analysis()

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
        self._said(text)
        await self._emit_audio(self.filler_audio[text], kind="filler")

    async def _emit_audio(self, chunk: bytes, kind: str = "speech") -> None:
        self._last_audio_kind = kind
        now = time.monotonic()
        self._speaking_until = max(self._speaking_until, now) + len(chunk) / 2 / self.sr
        await self.send_audio(chunk)

    async def _tts(self, sentence: str):
        # In turn-based STT mode (accounts limited to one active Gnani request) never synthesise while a
        # transcription request is in flight: TurnBasedStt exposes that as an asyncio.Lock named `busy`.
        lock = getattr(self._stt, "busy", None)
        if isinstance(lock, asyncio.Lock):
            async with lock:
                chunks = [c async for c in self._tts_unlocked(sentence)]
            for c in chunks:
                yield c
            return
        async for c in self._tts_unlocked(sentence):
            yield c

    async def _tts_unlocked(self, sentence: str):
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

    async def _reply_stream(self):
        """agent.reply_sentences, but the first sentence must arrive within first_sentence_timeout."""
        agen = self.agent.reply_sentences(list(self.history)).__aiter__()
        first = True
        try:
            while True:
                try:
                    if first and self.first_sentence_timeout:
                        sentence = await asyncio.wait_for(agen.__anext__(), self.first_sentence_timeout)
                    else:
                        sentence = await agen.__anext__()
                except StopAsyncIteration:
                    return
                first = False
                yield sentence
        finally:
            aclose = getattr(agen, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except Exception:
                    pass

    def _fallback_choice(self) -> str | None:
        """A pre-rendered line to say when a reply produced no audio (LLM error, timeout or empty reply)."""
        texts: list[str] = []
        if hasattr(self.agent, "fallback_texts"):
            try:
                texts = list(self.agent.fallback_texts() or [])
            except Exception as e:
                log.warning("fallback_texts failed: %r", e)
        options = [t for t in texts if t in self.filler_audio and t != self._last_filler]
        if not options:
            options = [t for t in self.agent.filler_texts() if t in self.filler_audio and t != self._last_filler]
        return self.rng.choice(options) if options else None

    async def _reply(self, after: asyncio.Task | None = None) -> None:
        if after is not None:  # listen_only: speak after the previous line (cancelling this cancels that one too)
            try:
                await asyncio.wait({after})
            except asyncio.CancelledError:
                after.cancel()
                raise
        if self.listen_only:
            self._reply_audio_started = False
        said: list[str] = []
        meta: dict = {}
        emitted = False
        cancelled = False
        try:
            async for sentence in self._reply_stream():
                said.append(sentence)
                self._said(sentence)
                async for chunk in self._tts(sentence):
                    if not self._reply_audio_started:
                        self._reply_audio_started = True
                        if self._filler_task and not self._filler_task.done():
                            self._filler_task.cancel()
                        await self._safe_json({"type": "agent_speaking", "on": True})
                    emitted = True
                    await self._emit_audio(chunk)
        except asyncio.CancelledError:
            cancelled = True
        except Exception as e:
            log.warning("reply failed: %r", e)
        if not cancelled and not emitted and not self._closing and not self.listen_only:
            # never leave the caller in dead air: say a pre-rendered "say that again?" line instead
            text = self._fallback_choice()
            if text:
                log.info("reply produced no audio; fallback line")
                try:
                    self._last_filler = text
                    self._said(text)
                    self._reply_audio_started = True
                    await self._safe_json({"type": "agent_speaking", "on": True})
                    await self._emit_audio(self.filler_audio[text])
                    said, meta = [text], {"fallback": True}
                except asyncio.CancelledError:
                    pass
        if said:
            text = " ".join(said)
            turn = Turn(self.agent.agent_label, text, round(self.now(), 2))
            self.history.append(turn)
            await self._record(turn)
            if not meta:
                meta = self.agent.turn_meta() if hasattr(self.agent, "turn_meta") else {}
            await self._safe_json({"type": "turn", "speaker": turn.speaker, "text": text, "t": turn.t, **meta})
        if said or not self.listen_only:  # a listen-only agent that said nothing sends nothing
            await self._finish_speaking()

    async def _finish_speaking(self) -> None:
        await self._safe_json({"type": "agent_speaking", "on": False})

    # ------------------------------------------------------------------ analysis + utils
    def _request_analysis(self) -> None:
        """Coalesce: while an analysis runs, newer turns only mark it dirty; it then runs once more on the latest
        history. Never a queue of LLM calls (a chatty caller would burn the LLM's tokens-per-minute budget)."""
        if self._analysis_task is not None and not self._analysis_task.done():
            self._analysis_dirty = True
            return
        self._analysis_task = self._spawn(self._analysis_loop())

    async def _analysis_loop(self) -> None:
        while True:
            self._analysis_dirty = False
            await self._analyse()
            if not self._analysis_dirty:
                return

    async def _analyse(self) -> None:
        async with self._analysis_lock:
            try:
                evt = await self.agent.on_user_turn(list(self.history))
            except Exception as e:
                log.warning("analysis failed: %r", e)
                return
            if isinstance(evt, dict):
                await self._safe_json(evt)

    def _spawn(self, coro) -> asyncio.Task:
        t = asyncio.create_task(coro)
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)
        return t

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
