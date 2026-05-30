import pytest
from hermes_evenhub_bridge.asr import REGISTRY, DEFAULT_ACTIVE, get_spec


def test_registry_contents():
    assert set(REGISTRY) == {
        "parakeet-tdt-0.6b-v2", "parakeet-tdt-0.6b-v3", "whisper-tiny"}
    assert REGISTRY["parakeet-tdt-0.6b-v2"].backend == "fluidaudio"
    assert REGISTRY["parakeet-tdt-0.6b-v2"].model_version == "v2"
    assert REGISTRY["whisper-tiny"].backend == "whisper"
    assert REGISTRY["whisper-tiny"].model_size == "tiny"


def test_default_active_is_parakeet_v2():
    assert DEFAULT_ACTIVE == "parakeet-tdt-0.6b-v2"


def test_get_spec_unknown_raises():
    with pytest.raises(KeyError):
        get_spec("nope")
