from hermes_evenhub_bridge.config import BridgeConfig


def test_from_env_picks_up_port(monkeypatch):
    monkeypatch.setenv("EVENHUB_BRIDGE_PORT", "9999")
    assert BridgeConfig.from_env().ws_port == 9999


def test_from_env_invalid_port_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("EVENHUB_BRIDGE_PORT", "not-int")
    assert BridgeConfig.from_env().ws_port == 8765


def test_from_env_out_of_range_port_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("EVENHUB_BRIDGE_PORT", "65536")
    assert BridgeConfig.from_env().ws_port == 8765


def test_from_env_allows_ephemeral_port(monkeypatch):
    monkeypatch.setenv("EVENHUB_BRIDGE_PORT", "0")
    assert BridgeConfig.from_env().ws_port == 0


def test_from_env_picks_up_token(monkeypatch):
    monkeypatch.setenv("EVENHUB_BRIDGE_TOKEN", "tok")
    cfg = BridgeConfig.from_env()
    assert cfg.token == "tok"


def test_from_env_defaults(monkeypatch):
    for key in ("EVENHUB_BRIDGE_HOST", "EVENHUB_BRIDGE_PORT", "EVENHUB_BRIDGE_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    cfg = BridgeConfig.from_env()
    assert cfg.ws_host == "0.0.0.0"
    assert cfg.ws_port == 8765
    assert cfg.token == ""
    assert not hasattr(cfg, "asr_model")
    assert not hasattr(cfg, "api_base")


def test_asr_sidecar_bin_default_and_override(monkeypatch):
    from hermes_evenhub_bridge.config import BridgeConfig
    monkeypatch.delenv("EVENHUB_ASR_SIDECAR_BIN", raising=False)
    cfg = BridgeConfig.from_env()
    assert cfg.asr_sidecar_bin.endswith("g2-asr-sidecar")
    monkeypatch.setenv("EVENHUB_ASR_SIDECAR_BIN", "/custom/bin")
    assert BridgeConfig.from_env().asr_sidecar_bin == "/custom/bin"


def test_asr_state_path_default(monkeypatch):
    from hermes_evenhub_bridge.config import BridgeConfig
    monkeypatch.delenv("EVENHUB_ASR_STATE", raising=False)
    assert BridgeConfig.from_env().asr_state_path.endswith("even_g2_asr.json")
