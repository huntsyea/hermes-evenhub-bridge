import logging
from hermes_evenhub_bridge.asr import FallbackTranscriber, ASRUnavailable


class Raising:
    def __init__(self): self.calls = 0
    def transcribe(self, pcm): self.calls += 1; raise ASRUnavailable("boom")
    def close(self): ...


class Fixed:
    def __init__(self, text): self.text = text; self.calls = 0
    def transcribe(self, pcm): self.calls += 1; return self.text
    def close(self): ...


def test_falls_back_when_primary_unavailable(caplog):
    primary, fallback = Raising(), Fixed("from whisper")
    ft = FallbackTranscriber(primary, fallback)
    with caplog.at_level(logging.WARNING):
        assert ft.transcribe(b"\x01\x02") == "from whisper"
    assert fallback.calls == 1
    assert any("boom" in r.message for r in caplog.records)


def test_primary_success_never_calls_fallback():
    primary, fallback = Fixed("from parakeet"), Fixed("from whisper")
    ft = FallbackTranscriber(primary, fallback)
    assert ft.transcribe(b"\x01\x02") == "from parakeet"
    assert fallback.calls == 0


def test_empty_pcm_short_circuits():
    primary, fallback = Fixed("x"), Fixed("y")
    ft = FallbackTranscriber(primary, fallback)
    assert ft.transcribe(b"") == ""
    assert primary.calls == 0 and fallback.calls == 0
