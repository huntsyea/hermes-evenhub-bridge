from hermes_evenhub_bridge.asr import ASRBackend, ASRUnavailable, WhisperBackend


def test_whisper_satisfies_backend_protocol():
    wb = WhisperBackend("tiny")
    assert isinstance(wb, ASRBackend)  # runtime_checkable structural check
    for name in ("is_installed", "ensure_downloaded", "transcribe", "close"):
        assert hasattr(wb, name)


def test_asr_unavailable_is_exception():
    assert issubclass(ASRUnavailable, Exception)
