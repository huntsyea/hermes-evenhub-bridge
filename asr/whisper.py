"""faster-whisper ASR backend. PCM in is s16le / 16 kHz / mono."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np


def pcm_to_float32(pcm_bytes: bytes) -> np.ndarray:
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0


class WhisperBackend:
    """Wraps faster-whisper's WhisperModel; model loads lazily on first use."""

    def __init__(self, model_size: str = "tiny", cache_dir: str | None = None) -> None:
        self._model_size = model_size
        self._model: Optional[object] = None
        # Default to the faster-whisper / HF cache location.
        self._cache_dir = Path(
            cache_dir
            or os.environ.get("HF_HOME")
            or (Path.home() / ".cache" / "huggingface")
        )

    def is_installed(self) -> bool:
        if self._model is not None:
            return True
        # faster-whisper caches under hub/models--Systran--faster-whisper-<size>
        hub = self._cache_dir / "hub"
        if not hub.exists():
            return False
        return any(self._model_size in p.name for p in hub.glob("models--*"))

    def ensure_downloaded(self) -> None:
        if self._model is None:
            self._load_model()

    def close(self) -> None:
        self._model = None

    def _load_model(self) -> None:
        import faster_whisper  # local import keeps startup fast

        # device="auto" picks CUDA when a GPU is present and then dies at
        # encode time without cuBLAS/cuDNN DLLs (RuntimeError: Library
        # cublas64_12.dll is not found). Default to CPU; opt back into GPU
        # via EVENHUB_WHISPER_DEVICE once the CUDA libraries are installed.
        device = os.environ.get("EVENHUB_WHISPER_DEVICE", "cpu")
        compute_type = os.environ.get(
            "EVENHUB_WHISPER_COMPUTE", "int8" if device == "cpu" else "default"
        )
        self._model = faster_whisper.WhisperModel(
            self._model_size, device=device, compute_type=compute_type
        )

    def transcribe(self, pcm_bytes: bytes) -> str:
        if not pcm_bytes:
            return ""
        if self._model is None:
            self._load_model()
        audio = pcm_to_float32(pcm_bytes)
        segments, _info = self._model.transcribe(audio)  # type: ignore[union-attr]
        return "".join(seg.text for seg in segments).strip()

