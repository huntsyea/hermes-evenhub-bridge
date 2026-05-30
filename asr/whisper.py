"""faster-whisper ASR backend. PCM in is s16le / 16 kHz / mono."""
from __future__ import annotations

from typing import Optional

import numpy as np


def pcm_to_float32(pcm_bytes: bytes) -> np.ndarray:
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0


class WhisperBackend:
    """Wraps faster-whisper's WhisperModel; model loads lazily on first use."""

    def __init__(self, model_size: str = "tiny") -> None:
        self._model_size = model_size
        self._model: Optional[object] = None

    def _load_model(self) -> None:
        import faster_whisper  # local import keeps startup fast

        self._model = faster_whisper.WhisperModel(self._model_size)

    def transcribe(self, pcm_bytes: bytes) -> str:
        if not pcm_bytes:
            return ""
        if self._model is None:
            self._load_model()
        audio = pcm_to_float32(pcm_bytes)
        segments, _info = self._model.transcribe(audio)  # type: ignore[union-attr]
        return "".join(seg.text for seg in segments).strip()


# Temporary back-compat alias; removed in a later task.
Transcriber = WhisperBackend
