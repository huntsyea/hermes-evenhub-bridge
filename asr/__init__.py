"""Pluggable ASR: backends, registry, active-model resolution, fallback."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .whisper import WhisperBackend, pcm_to_float32

log = logging.getLogger("hermes-evenhub-bridge")


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


@dataclass(frozen=True)
class ModelSpec:
    backend: str                      # "fluidaudio" | "whisper"
    lang: str                         # "en" | "multi"
    model_version: str | None = None  # fluidaudio: "v2" | "v3"
    model_size: str | None = None     # whisper: "tiny" | "base" | ...


REGISTRY: dict[str, ModelSpec] = {
    "parakeet-tdt-0.6b-v2": ModelSpec("fluidaudio", "en", model_version="v2"),
    "parakeet-tdt-0.6b-v3": ModelSpec("fluidaudio", "multi", model_version="v3"),
    "whisper-tiny":         ModelSpec("whisper", "multi", model_size="tiny"),
}
DEFAULT_ACTIVE = "parakeet-tdt-0.6b-v2"


def get_spec(name: str) -> ModelSpec:
    return REGISTRY[name]


def load_active(bridge_cfg) -> FallbackTranscriber:
    """Build the active ASR backend with whisper-tiny fallback.

    Phase 1: whisper both ways. A later task swaps the primary for the
    registry-selected backend (e.g. FluidAudioBackend) while keeping this signature.
    """
    size = getattr(bridge_cfg, "asr_model", "tiny") or "tiny"
    primary = WhisperBackend(size)
    fallback = WhisperBackend("tiny")
    return FallbackTranscriber(primary, fallback)


__all__ = [
    "ASRBackend", "ASRUnavailable", "FallbackTranscriber",
    "WhisperBackend", "pcm_to_float32", "load_active",
    "ModelSpec", "REGISTRY", "DEFAULT_ACTIVE", "get_spec",
]

# Temporary back-compat alias; removed in a later task.
Transcriber = WhisperBackend  # noqa: F401
