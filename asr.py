"""
ASR module — wraps faster-whisper to transcribe raw PCM audio bytes.

PCM format from G2 glasses: signed 16-bit little-endian (s16le), 16 kHz, mono.
"""

from __future__ import annotations

from typing import Optional

import numpy as np


def pcm_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convert s16le PCM bytes to a float32 numpy array normalized to [-1.0, 1.0].

    Args:
        pcm_bytes: Raw signed 16-bit little-endian PCM audio bytes.

    Returns:
        A float32 numpy array with values in [-1.0, 1.0].
    """
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0


class Transcriber:
    """Wraps faster-whisper's WhisperModel to transcribe raw PCM audio.

    The model is loaded lazily on the first call to :meth:`transcribe` so that
    importing this module does not trigger a (potentially slow) model download.
    """

    def __init__(self, model_size: str = "base") -> None:
        self._model_size = model_size
        self._model: Optional[object] = None

    def _load_model(self) -> None:
        """Instantiate the WhisperModel (called once, on first use)."""
        import faster_whisper  # local import keeps startup fast

        self._model = faster_whisper.WhisperModel(self._model_size)

    def transcribe(self, pcm_bytes: bytes) -> str:
        """Transcribe raw s16le/16kHz/mono PCM bytes to text.

        Args:
            pcm_bytes: Raw PCM audio in s16le format at 16 kHz mono.

        Returns:
            Transcribed text as a single stripped string, or ``""`` for
            empty/silent input.
        """
        if not pcm_bytes:
            return ""

        if self._model is None:
            self._load_model()

        audio = pcm_to_float32(pcm_bytes)
        segments, _info = self._model.transcribe(audio)  # type: ignore[union-attr]

        return "".join(seg.text for seg in segments).strip()
