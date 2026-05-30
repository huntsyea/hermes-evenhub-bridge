import json

import hermes_evenhub_bridge.net as net
from hermes_evenhub_bridge.config import BridgeConfig

SAMPLE_STATUS = {
    "Self": {
        "TailscaleIPs": ["100.101.102.103", "fd7a::1"],
        "DNSName": "my-mac.tailnet-abc.ts.net.",
        "Online": True,
    }
}


def test_detect_tailscale_parses_status(monkeypatch):
    monkeypatch.setattr(net, "_tailscale_bin", lambda: "/usr/bin/tailscale")

    class R:
        returncode = 0
        stdout = json.dumps(SAMPLE_STATUS)

    monkeypatch.setattr(net.subprocess, "run", lambda *a, **k: R())
    info = net.detect_tailscale()
    assert info["ip"] == "100.101.102.103"
    assert info["magic_dns"] == "my-mac.tailnet-abc.ts.net"  # trailing dot stripped
    assert info["online"] is True


def test_detect_tailscale_none_when_binary_absent(monkeypatch):
    monkeypatch.setattr(net, "_tailscale_bin", lambda: None)
    assert net.detect_tailscale() is None


def test_preferred_url_prefers_magicdns():
    cfg = BridgeConfig(ws_port=8765, net_mode="both")
    ts = {"ip": "100.1.2.3", "magic_dns": "host.ts.net", "online": True}
    assert net.preferred_connect_url(cfg, ts) == "ws://host.ts.net:8765"


def test_preferred_url_falls_back_to_ip_then_lan(monkeypatch):
    monkeypatch.setattr(net, "lan_ip", lambda: "192.168.1.50")
    # No MagicDNS -> Tailscale IP.
    cfg = BridgeConfig(ws_port=9000, net_mode="both")
    assert net.preferred_connect_url(
        cfg, {"ip": "100.9.9.9", "magic_dns": "", "online": True}
    ) == "ws://100.9.9.9:9000"
    # lan mode ignores Tailscale entirely -> LAN IP.
    cfg_lan = BridgeConfig(ws_port=9000, net_mode="lan")
    assert net.preferred_connect_url(
        cfg_lan, {"ip": "100.9.9.9", "magic_dns": "host.ts.net"}
    ) == "ws://192.168.1.50:9000"


def test_detect_tailscale_none_when_offline(monkeypatch):
    monkeypatch.setattr(net, "_tailscale_bin", lambda: "/usr/bin/tailscale")
    offline = {"Self": {"TailscaleIPs": ["100.1.1.1"], "DNSName": "h.ts.net.", "Online": False}}

    class R:
        returncode = 0
        stdout = json.dumps(offline)

    # status --json says offline; fall back path (`tailscale ip -4`) returns nothing.
    class Empty:
        returncode = 1
        stdout = ""

    calls = iter([R(), Empty()])
    monkeypatch.setattr(net.subprocess, "run", lambda *a, **k: next(calls))
    assert net.detect_tailscale() is None


def test_preferred_url_brackets_ipv6():
    cfg = BridgeConfig(ws_port=8765, net_mode="both")
    ts = {"ip": "fd7a::1", "magic_dns": "", "online": True}
    assert net.preferred_connect_url(cfg, ts) == "ws://[fd7a::1]:8765"


def test_preferred_url_uses_pinned_host_over_tailscale(monkeypatch):
    monkeypatch.setattr(net, "lan_ip", lambda: "10.0.0.9")
    cfg = BridgeConfig(ws_host="192.168.1.7", ws_port=8765, net_mode="both")
    ts = {"ip": "100.1.2.3", "magic_dns": "host.ts.net", "online": True}
    # Pinned bind host wins so the advertised URL matches the bound interface.
    assert net.preferred_connect_url(cfg, ts) == "ws://192.168.1.7:8765"


def test_resolve_skips_tailscale_in_lan_mode(monkeypatch):
    monkeypatch.setattr(net, "lan_ip", lambda: "10.0.0.9")

    def boom():
        raise AssertionError("must not probe tailscale in lan mode")

    monkeypatch.setattr(net, "detect_tailscale", boom)
    cfg = BridgeConfig(ws_host="0.0.0.0", ws_port=8765, net_mode="lan")
    bind, url, ts = net.resolve(cfg)
    assert ts is None and bind == "0.0.0.0" and url == "ws://10.0.0.9:8765"


def test_bind_host_modes(monkeypatch):
    monkeypatch.setattr(net, "detect_tailscale", lambda: None)
    ts = {"ip": "100.5.5.5", "magic_dns": "h.ts.net", "online": True}
    assert net.bind_host(BridgeConfig(ws_host="0.0.0.0", net_mode="both"), ts) == "0.0.0.0"
    assert net.bind_host(BridgeConfig(ws_host="0.0.0.0", net_mode="tailnet"), ts) == "100.5.5.5"
    assert net.bind_host(BridgeConfig(ws_host="0.0.0.0", net_mode="lan"), ts) == "0.0.0.0"
    # tailnet requested but no tailnet present -> configured host.
    assert net.bind_host(BridgeConfig(ws_host="0.0.0.0", net_mode="tailnet"), None) == "0.0.0.0"
