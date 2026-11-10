"""Thin clients for Gnani AI's speech APIs (host https://api.vachana.ai)."""

from . import gate
from .errors import GnaniError
from .gate import gnani_call, gnani_slot, is_rate_limit
from .stt_rest import STT_REST_URL, transcribe_rest
from .stt_stream import STT_WS_URL, PrismaStream, SttEvent, build_stt_headers, parse_stt_message
from .tts import (
    AUDIO_TAGS,
    TtsCache,
    TtsError,
    build_tts_body,
    create_voice_embedding,
    normalise_embedding,
    strip_audio_tags,
    tts_clone_rest,
    tts_rest,
    tts_stream,
)

__all__ = [
    "AUDIO_TAGS", "GnaniError", "gate", "gnani_call", "gnani_slot", "is_rate_limit", "PrismaStream", "STT_REST_URL", "STT_WS_URL", "SttEvent",
    "TtsCache", "TtsError", "build_stt_headers", "build_tts_body", "create_voice_embedding",
    "normalise_embedding", "parse_stt_message", "strip_audio_tags", "transcribe_rest",
    "tts_clone_rest", "tts_rest", "tts_stream",
]
