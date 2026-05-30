"""Pluggable ASR: backends, registry, active-model resolution, fallback."""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from .whisper import WhisperBackend, pcm_to_float32

log = logging.getLogger("hermes-evenhub-bridge")

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


class FallbackTranscriber:
    """Tries the active backend; on ASRUnavailable (or any error) uses the fallback."""

    def __init__(self, primary: ASRBackend, fallback: ASRBackend) -> None:
        self._primary = primary
        self._fallback = fallback

    def transcribe(self, pcm: bytes) -> str:
        if not pcm:
            return ""
        try:
            return self._primary.transcribe(pcm)
        except ASRUnavailable as e:
            log.warning("ASR primary unavailable (%s); falling back to whisper", e)
        except Exception as e:  # defensive: never let ASR kill a turn
            log.warning("ASR primary error (%s); falling back to whisper", e)
        return self._fallback.transcribe(pcm)

    def close(self) -> None:
        for b in (self._primary, self._fallback):
            try:
                b.close()
            except Exception:
                pass


__all__ = ["ASRBackend", "ASRUnavailable", "FallbackTranscriber", "WhisperBackend", "pcm_to_float32", "Transcriber"]
