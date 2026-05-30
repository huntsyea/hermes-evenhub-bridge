"""Pluggable ASR: backends, registry, active-model resolution, fallback."""
from __future__ import annotations

import logging
import os
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


def _build_backend(name: str, bridge_cfg):
    from .fluidaudio import FluidAudioBackend  # lazy import to avoid a cycle
    spec = REGISTRY[name]
    if spec.backend == "whisper":
        return WhisperBackend(spec.model_size or "tiny")
    from ..config import default_sidecar_bin
    return FluidAudioBackend(
        binary_path=getattr(bridge_cfg, "asr_sidecar_bin", "") or default_sidecar_bin(),
        model_version=spec.model_version or "v2",
    )


def resolve_active_name(bridge_cfg) -> str:
    from .state import get_active
    name = os.environ.get("EVENHUB_ASR_MODEL")
    if not name:
        name = get_active(getattr(bridge_cfg, "asr_state_path", "") or "")
    if not name or name not in REGISTRY:
        if name:
            log.warning("unknown ASR model %r; using default %s", name, DEFAULT_ACTIVE)
        name = DEFAULT_ACTIVE
    return name


def load_active(bridge_cfg) -> FallbackTranscriber:
    """Build the active ASR backend with whisper-tiny fallback.

    Resolves: env EVENHUB_ASR_MODEL > state file > DEFAULT_ACTIVE.
    Unknown names fall back to DEFAULT_ACTIVE (never raises).
    """
    name = resolve_active_name(bridge_cfg)
    primary = _build_backend(name, bridge_cfg)
    fallback = WhisperBackend("tiny")
    return FallbackTranscriber(primary, fallback)


__all__ = [
    "ASRBackend", "ASRUnavailable", "FallbackTranscriber",
    "WhisperBackend", "pcm_to_float32", "load_active", "resolve_active_name",
    "ModelSpec", "REGISTRY", "DEFAULT_ACTIVE", "get_spec",
]
