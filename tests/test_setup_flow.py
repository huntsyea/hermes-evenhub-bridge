import subprocess

from hermes_evenhub_bridge.config import BridgeConfig
from hermes_evenhub_bridge import setup_flow


def test_setup_status_reports_no_token_value(monkeypatch):
    monkeypatch.setattr(setup_flow.net, "tailscale_status", lambda: {
        "installed": True,
        "online": True,
        "binary": "/usr/bin/tailscale",
        "ip": "100.1.2.3",
        "magic_dns": "host.tailnet.ts.net",
    })
    cfg = BridgeConfig(token="secret", ws_host="127.0.0.1", net_mode="lan")
    status = setup_flow.setup_status(cfg)
    assert status["token_configured"] is True
    assert "secret" not in str(status)
    assert status["public_url"] == ""
    assert status["candidate_public_url"] == "wss://host.tailnet.ts.net:8443"
    assert status["restart_required_for_config"] is False


def test_configure_local_bridge_generates_and_persists_token(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    cfg = BridgeConfig(ws_host="0.0.0.0", ws_port=9000, token="", net_mode="both")
    result = setup_flow.configure_local_bridge(cfg=cfg, token_factory=lambda: "generated-token")
    assert result["token"] == "generated-token"
    assert result["restart_required"] is True
    env_text = (tmp_path / ".env").read_text()
    assert "EVENHUB_BRIDGE_TOKEN=generated-token" in env_text
    assert "EVENHUB_BRIDGE_HOST=127.0.0.1" in env_text
    assert "EVENHUB_BRIDGE_NET=lan" in env_text
    assert "EVENHUB_BRIDGE_PORT=9000" in env_text


def test_enable_tailscale_serve_runs_serve_without_shell(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(setup_flow.net, "_tailscale_bin", lambda: "/usr/bin/tailscale")
    monkeypatch.setattr(setup_flow.net, "tailscale_status", lambda: {
        "installed": True,
        "online": True,
        "binary": "/usr/bin/tailscale",
        "ip": "100.1.2.3",
        "magic_dns": "host.tailnet.ts.net",
    })
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    result = setup_flow.enable_tailscale_serve(
        cfg=BridgeConfig(ws_port=9000),
        serve_port=9443,
        runner=runner,
    )
    assert calls[0][0] == [
        "/usr/bin/tailscale",
        "serve",
        "--https=9443",
        "--bg",
        "http://127.0.0.1:9000",
    ]
    assert calls[0][1]["timeout"] == 15
    assert result["public_url"] == "wss://host.tailnet.ts.net:9443"
    env_text = (tmp_path / ".env").read_text()
    assert "EVENHUB_BRIDGE_PUBLIC_URL=wss://host.tailnet.ts.net:9443" in env_text


def test_enable_tailscale_serve_requires_magicdns(monkeypatch):
    monkeypatch.setattr(setup_flow.net, "tailscale_status", lambda: {
        "installed": True,
        "online": True,
        "binary": "/usr/bin/tailscale",
        "ip": "100.1.2.3",
        "magic_dns": "",
    })
    try:
        setup_flow.enable_tailscale_serve(cfg=BridgeConfig())
    except setup_flow.SetupError as exc:
        assert "MagicDNS" in str(exc)
    else:
        raise AssertionError("expected setup failure")
