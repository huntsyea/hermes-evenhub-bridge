import pytest as _pytest
_pytest.importorskip("gateway")  # gateway-dependent module
pytestmark = _pytest.mark.gateway

import json, pytest
from gateway.config import PlatformConfig
from hermes_evenhub_bridge.adapter import EvenG2Adapter
from hermes_evenhub_bridge.config import BridgeConfig
from hermes_evenhub_bridge.asr import ASRUnavailable, FallbackTranscriber


class FakeWS:
    def __init__(self): self.sent = []
    async def send(self, d): self.sent.append(json.loads(d))


class FakeTranscriber:
    def transcribe(self, pcm: bytes) -> str:
        return "hello from voice" if pcm else ""
    def close(self): ...


def _adapter(tmp_path):
    a = EvenG2Adapter(PlatformConfig(extra={}),
                      bridge_cfg=BridgeConfig(token="t"),
                      status_path=tmp_path / "s.json")
    a._transcriber = FakeTranscriber()
    return a


@pytest.mark.asyncio
async def test_on_audio_emits_transcript(tmp_path, monkeypatch):
    a = _adapter(tmp_path)
    # Pin the active name so _get_transcriber keeps the injected FakeTranscriber.
    a._active_name = "fake"
    monkeypatch.setattr("hermes_evenhub_bridge.adapter.resolve_active_name",
                        lambda cfg: "fake", raising=False)
    ws = FakeWS(); a._registry.register("g2", ws)
    await a.on_audio("g2", b"\x01\x02")
    assert any(m["t"] == "transcript" and m["text"] == "hello from voice"
               for m in ws.sent)


@pytest.mark.asyncio
async def test_on_audio_empty_is_safe(tmp_path, monkeypatch):
    a = _adapter(tmp_path)
    a._active_name = "fake"
    monkeypatch.setattr("hermes_evenhub_bridge.adapter.resolve_active_name",
                        lambda cfg: "fake", raising=False)
    ws = FakeWS(); a._registry.register("g2", ws)
    await a.on_audio("g2", b"")
    assert any(m["t"] == "transcript" and m["text"] == "" for m in ws.sent)


class _RaisingBackend:
    def transcribe(self, pcm): raise ASRUnavailable("no sidecar")
    def close(self): ...


class _FixedBackend:
    def __init__(self, text): self.text = text
    def transcribe(self, pcm): return self.text
    def close(self): ...


@pytest.mark.asyncio
async def test_on_audio_falls_back_to_whisper_when_primary_unavailable(tmp_path, monkeypatch):
    # The adapter builds a FallbackTranscriber via load_active; a failing primary
    # must still yield a transcript from the fallback backend.
    a = _adapter(tmp_path)
    a._transcriber = FallbackTranscriber(_RaisingBackend(), _FixedBackend("whisper text"))
    a._active_name = "fake"
    monkeypatch.setattr("hermes_evenhub_bridge.adapter.resolve_active_name",
                        lambda cfg: "fake", raising=False)
    ws = FakeWS(); a._registry.register("g2", ws)
    await a.on_audio("g2", b"\x01\x02")
    assert any(m["t"] == "transcript" and m["text"] == "whisper text"
               for m in ws.sent)


@pytest.mark.asyncio
async def test_active_model_change_rebuilds_backend(tmp_path, monkeypatch):
    a = _adapter(tmp_path)

    class Tracked:
        def __init__(self, tag): self.tag = tag; self.closed = False
        def transcribe(self, pcm): return self.tag
        def close(self): self.closed = True

    built = []
    names = iter(["one", "two"])

    def fake_load(cfg):
        t = Tracked(next(names)); built.append(t); return t

    def fake_resolve(cfg):
        return "parakeet-tdt-0.6b-v2" if len(built) == 0 else "whisper-tiny"

    monkeypatch.setattr("hermes_evenhub_bridge.adapter.load_active", fake_load, raising=False)
    monkeypatch.setattr("hermes_evenhub_bridge.adapter.resolve_active_name", fake_resolve, raising=False)
    a._transcriber = None  # force resolution path

    ws = FakeWS(); a._registry.register("g2", ws)
    await a.on_audio("g2", b"\x01")   # builds "one"
    await a.on_audio("g2", b"\x01")   # active changed -> closes "one", builds "two"
    assert built[0].closed is True
    assert len(built) == 2


@pytest.mark.asyncio
async def test_get_transcriber_records_active_name_in_status(tmp_path, monkeypatch):
    a = _adapter(tmp_path)
    a._transcriber = None  # force rebuild path

    recorded = []

    original_update = a._status.update

    def capturing_update(**fields):
        recorded.append(fields)
        original_update(**fields)

    a._status.update = capturing_update

    monkeypatch.setattr("hermes_evenhub_bridge.adapter.resolve_active_name",
                        lambda cfg: "whisper-tiny", raising=False)
    monkeypatch.setattr("hermes_evenhub_bridge.adapter.load_active",
                        lambda cfg: FakeTranscriber(), raising=False)

    ws = FakeWS(); a._registry.register("g2", ws)
    await a.on_audio("g2", b"\x01\x02")

    asr_updates = [f for f in recorded if "asr_active" in f]
    assert asr_updates, "status.update was never called with asr_active"
    assert asr_updates[-1]["asr_active"] == "whisper-tiny"
