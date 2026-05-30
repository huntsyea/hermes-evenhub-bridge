import hermes_evenhub_bridge as pkg


def test_none_without_token(monkeypatch):
    monkeypatch.delenv("EVENHUB_BRIDGE_TOKEN", raising=False)
    assert pkg._env_enablement() is None


def test_returns_host_port_with_token(monkeypatch):
    monkeypatch.setenv("EVENHUB_BRIDGE_TOKEN", "x")
    monkeypatch.setenv("EVENHUB_BRIDGE_PORT", "9000")
    monkeypatch.delenv("EVENHUB_BRIDGE_HOST", raising=False)
    assert pkg._env_enablement() == {"host": "0.0.0.0", "port": 9000}


def test_invalid_port_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("EVENHUB_BRIDGE_TOKEN", "x")
    monkeypatch.setenv("EVENHUB_BRIDGE_PORT", "not-int")
    monkeypatch.delenv("EVENHUB_BRIDGE_HOST", raising=False)
    assert pkg._env_enablement() == {"host": "0.0.0.0", "port": 8765}


def test_out_of_range_port_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("EVENHUB_BRIDGE_TOKEN", "x")
    monkeypatch.setenv("EVENHUB_BRIDGE_PORT", "-1")
    monkeypatch.delenv("EVENHUB_BRIDGE_HOST", raising=False)
    assert pkg._env_enablement() == {"host": "0.0.0.0", "port": 8765}
