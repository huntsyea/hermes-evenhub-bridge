"""Pluggable ASR: backends, registry, active-model resolution, fallback."""
from __future__ import annotations

from .whisper import WhisperBackend, pcm_to_float32

# Temporary back-compat alias; removed in a later task.
from .whisper import WhisperBackend as Transcriber

__all__ = ["WhisperBackend", "pcm_to_float32", "Transcriber"]
