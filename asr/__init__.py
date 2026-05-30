"""Pluggable ASR: backends, registry, active-model resolution, fallback."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .whisper import WhisperBackend, pcm_to_float32

# Temporary back-compat alias; removed in a later task.
from .whisper import WhisperBackend as Transcriber


class ASRUnavailable(RuntimeError):
    """Raised by a backend when it cannot transcribe (not built, model missing, crash)."""


@runtime_checkable
class ASRBackend(Protocol):
    def is_installed(self) -> bool: ...
    def ensure_downloaded(self) -> None: ...
    def transcribe(self, pcm: bytes) -> str: ...
    def close(self) -> None: ...


__all__ = ["ASRBackend", "ASRUnavailable", "WhisperBackend", "pcm_to_float32", "Transcriber"]
