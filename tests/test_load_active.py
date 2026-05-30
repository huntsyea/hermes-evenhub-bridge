from hermes_evenhub_bridge.asr import load_active, FallbackTranscriber
from hermes_evenhub_bridge.asr.fluidaudio import FluidAudioBackend
from hermes_evenhub_bridge.asr.whisper import WhisperBackend
from hermes_evenhub_bridge.asr.state import set_active
from hermes_evenhub_bridge.config import BridgeConfig


def _cfg(tmp_path, **kw):
    return BridgeConfig(token="t", asr_state_path=str(tmp_path / "asr.json"), **kw)


def test_env_overrides_state_and_default(tmp_path, monkeypatch):
    set_active("whisper-tiny", tmp_path / "asr.json")
    monkeypatch.setenv("EVENHUB_ASR_MODEL", "parakeet-tdt-0.6b-v3")
    ft = load_active(_cfg(tmp_path))
    assert isinstance(ft, FallbackTranscriber)
    assert isinstance(ft._primary, FluidAudioBackend)
    assert ft._primary._version == "v3"


def test_state_used_when_no_env(tmp_path, monkeypatch):
    monkeypatch.delenv("EVENHUB_ASR_MODEL", raising=False)
    set_active("whisper-tiny", tmp_path / "asr.json")
    ft = load_active(_cfg(tmp_path))
    assert isinstance(ft._primary, WhisperBackend)


def test_default_when_nothing_set(tmp_path, monkeypatch):
    monkeypatch.delenv("EVENHUB_ASR_MODEL", raising=False)
    ft = load_active(_cfg(tmp_path))
    assert isinstance(ft._primary, FluidAudioBackend)  # DEFAULT_ACTIVE = parakeet v2
    assert isinstance(ft._fallback, WhisperBackend)


def test_unknown_name_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENHUB_ASR_MODEL", "bogus")
    ft = load_active(_cfg(tmp_path))
    assert isinstance(ft._primary, FluidAudioBackend)  # never raises
