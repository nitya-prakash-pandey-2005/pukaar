"""One app-wide gate for Gnani's short requests, with retries.

Live check (Sun 8 Nov 2026): a key allows ONE short request at a time; a second concurrent REST call gets
`429 RATE_LIMITED`. An open Prisma streaming socket plus a TTS request at the same time was allowed, so the
long-lived STT stream is not gated. Everything else (TTS REST and WebSocket, STT REST, voice-clone embedding
and cloned TTS) goes through `gnani_slot()` and retries rate limits and 5xx with a short backoff.

`GNANI_MAX_CONCURRENT` (env, default 1) raises the limit if Gnani's quota allows more.
A holder can never block the app forever: after `GATE_TIMEOUT` seconds a waiter goes ahead anyway and relies
on the retries (this also rules out deadlocks if a caller does gated work while consuming a TTS stream).
"""

from __future__ import annotations

import asyncio
import logging
import os
import weakref
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, TypeVar

from .errors import GnaniError

log = logging.getLogger(__name__)
T = TypeVar("T")

MAX_CONCURRENT = max(1, int(os.environ.get("GNANI_MAX_CONCURRENT", "1") or 1))
RETRY_DELAYS: tuple[float, ...] = (0.5, 1.0, 2.0)
GATE_TIMEOUT = 20.0

_sems: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _sem() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _sems.get(loop)
    if sem is None:
        sem = _sems[loop] = asyncio.Semaphore(MAX_CONCURRENT)
    return sem


@asynccontextmanager
async def gnani_slot(timeout: float | None = None):
    """Holds the app's Gnani request slot for the duration of the block."""
    sem = _sem()
    try:
        await asyncio.wait_for(sem.acquire(), GATE_TIMEOUT if timeout is None else timeout)
        held = True
    except TimeoutError:
        log.warning("Gnani gate busy for %.0fs; sending anyway", GATE_TIMEOUT if timeout is None else timeout)
        held = False
    try:
        yield
    finally:
        if held:
            sem.release()


def _status(exc: BaseException) -> int | None:
    if isinstance(exc, GnaniError):
        return exc.status
    resp = getattr(exc, "response", None)  # websockets.InvalidStatus
    code = getattr(resp, "status_code", None) or getattr(exc, "status_code", None)  # legacy InvalidStatusCode
    return code if isinstance(code, int) else None


def is_rate_limit(exc: BaseException) -> bool:
    """True for errors worth retrying: 429/5xx (REST or WebSocket handshake) or a rate-limit message."""
    code = _status(exc)
    if code is not None:
        return code in (429, 500, 502, 503, 504)
    msg = str(exc).lower()
    return "429" in msg or ("rate" in msg and "limit" in msg) or "active request" in msg


async def gnani_call(fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
    """Runs one short Gnani request inside the gate; retries rate limits / 5xx (the slot is freed while waiting)."""
    delays = RETRY_DELAYS
    for attempt in range(len(delays) + 1):
        try:
            async with gnani_slot():
                return await fn(*args, **kwargs)
        except Exception as e:
            if attempt == len(delays) or not is_rate_limit(e):
                raise
            log.info("Gnani busy (%r); retry %d in %.1fs", e, attempt + 1, delays[attempt])
        await asyncio.sleep(delays[attempt])
    raise AssertionError("unreachable")
