"""
TDD tests for asr.py — pcm_to_float32 conversion, WhisperBackend class,
lazy model loading, mock-based transcribe, and empty-input handling.
"""

import struct
import numpy as np
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# pcm_to_float32 tests
# ---------------------------------------------------------------------------

def test_pcm_to_float32_silence():
    """All-zero bytes should produce an all-zero float32 array."""
    from hermes_evenhub_bridge.asr import pcm_to_float32

    pcm = b"\x00\x00" * 16  # 16 silent samples
    result = pcm_to_float32(pcm)

    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert len(result) == 16
    np.testing.assert_array_equal(result, np.zeros(16, dtype=np.float32))


def test_pcm_to_float32_max_positive():
    """0x7FFF (32767) should normalize to ~1.0 (within float32 precision)."""
    from hermes_evenhub_bridge.asr import pcm_to_float32

    # s16le: 0x7FFF = 32767
    pcm = struct.pack("<h", 32767)
    result = pcm_to_float32(pcm)

    assert result.dtype == np.float32
    assert len(result) == 1
    assert abs(result[0] - 1.0) < 1e-4


def test_pcm_to_float32_max_negative():
    """0x8000 (-32768) should normalize to -1.0."""
    from hermes_evenhub_bridge.asr import pcm_to_float32

    # s16le: 0x8000 = -32768
    pcm = struct.pack("<h", -32768)
    result = pcm_to_float32(pcm)

    assert result.dtype == np.float32
    assert len(result) == 1
    assert abs(result[0] - (-1.0)) < 1e-4


def test_pcm_to_float32_multiple_samples():
    """Multiple samples should decode in order."""
    from hermes_evenhub_bridge.asr import pcm_to_float32

    samples = [0, 16384, -16384, 32767]
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    result = pcm_to_float32(pcm)

    assert len(result) == len(samples)
    assert result.dtype == np.float32
    # 0 → 0.0, 16384 → ~0.5, -16384 → ~-0.5, 32767 → ~1.0
    assert abs(result[0]) < 1e-6
    assert abs(result[1] - (16384 / 32768.0)) < 1e-4
    assert abs(result[2] - (-16384 / 32768.0)) < 1e-4
    assert abs(result[3] - 1.0) < 1e-4


# ---------------------------------------------------------------------------
# WhisperBackend lazy-loading tests
# ---------------------------------------------------------------------------

def test_transcriber_model_not_loaded_at_init():
    """Model should NOT be loaded (downloaded) at __init__ time."""
    from hermes_evenhub_bridge.asr import WhisperBackend

    with patch("faster_whisper.WhisperModel") as mock_cls:
        t = WhisperBackend(model_size="tiny")
        mock_cls.assert_not_called()
        # Internal attribute confirming lazy state
        assert t._model is None


def test_transcriber_model_loaded_on_first_transcribe():
    """Model should be loaded on the first transcribe() call."""
    from hermes_evenhub_bridge.asr import WhisperBackend

    fake_segment = MagicMock()
    fake_segment.text = " hello world"
    fake_info = MagicMock()

    with patch("faster_whisper.WhisperModel") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.transcribe.return_value = (iter([fake_segment]), fake_info)
        mock_cls.return_value = mock_instance

        t = WhisperBackend(model_size="tiny")
        assert t._model is None  # not loaded yet

        pcm = b"\x00\x00" * 1600  # 0.1 s of silence at 16 kHz
        t.transcribe(pcm)

        mock_cls.assert_called_once()
        assert t._model is mock_instance


def test_transcriber_model_not_reloaded_on_second_transcribe():
    """Model should only be instantiated once across multiple calls."""
    from hermes_evenhub_bridge.asr import WhisperBackend

    fake_segment = MagicMock()
    fake_segment.text = " hi"
    fake_info = MagicMock()

    with patch("faster_whisper.WhisperModel") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.transcribe.return_value = (iter([fake_segment]), fake_info)
        mock_cls.return_value = mock_instance

        t = WhisperBackend(model_size="tiny")
        pcm = b"\x00\x00" * 1600

        # Reset side_effect so each call returns a fresh iterator
        def make_result():
            return (iter([fake_segment]), fake_info)

        mock_instance.transcribe.side_effect = lambda *a, **kw: make_result()

        t.transcribe(pcm)
        t.transcribe(pcm)

        assert mock_cls.call_count == 1


# ---------------------------------------------------------------------------
# WhisperBackend.transcribe with mock
# ---------------------------------------------------------------------------

def test_transcribe_returns_concatenated_text():
    """transcribe() should join segment texts and return them stripped."""
    from hermes_evenhub_bridge.asr import WhisperBackend

    seg1 = MagicMock()
    seg1.text = " Hello"
    seg2 = MagicMock()
    seg2.text = " world"
    fake_info = MagicMock()

    with patch("faster_whisper.WhisperModel") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.transcribe.return_value = (iter([seg1, seg2]), fake_info)
        mock_cls.return_value = mock_instance

        t = WhisperBackend(model_size="tiny")
        pcm = struct.pack("<h", 1000) * 1600
        result = t.transcribe(pcm)

    assert result == "Hello world"


def test_transcribe_passes_float32_array_to_model():
    """transcribe() should pass a float32 numpy array to model.transcribe()."""
    from hermes_evenhub_bridge.asr import WhisperBackend

    fake_info = MagicMock()

    with patch("faster_whisper.WhisperModel") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.transcribe.return_value = (iter([]), fake_info)
        mock_cls.return_value = mock_instance

        t = WhisperBackend(model_size="tiny")
        pcm = b"\x00\x00" * 3200  # 0.2 s
        t.transcribe(pcm)

        call_args = mock_instance.transcribe.call_args
        audio_arg = call_args[0][0]  # first positional argument

    assert isinstance(audio_arg, np.ndarray)
    assert audio_arg.dtype == np.float32
    assert len(audio_arg) == 3200


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

def test_transcribe_empty_bytes_returns_empty_string():
    """transcribe(b'') should return '' immediately without loading the model."""
    from hermes_evenhub_bridge.asr import WhisperBackend

    with patch("faster_whisper.WhisperModel") as mock_cls:
        t = WhisperBackend(model_size="tiny")
        result = t.transcribe(b"")

        assert result == ""
        mock_cls.assert_not_called()  # model should not be loaded for empty input
