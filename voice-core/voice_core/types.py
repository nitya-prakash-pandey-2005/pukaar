"""Small shared data types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Turn:
    """One utterance in a conversation.

    speaker is a free label such as "scammer", "dadi", "caller", "pukaar" or "user".
    t is seconds since the session started.
    """

    speaker: str
    text: str
    t: float
    lang: str | None = None
    latency_ms: float | None = None
