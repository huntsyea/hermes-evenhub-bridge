"""Network address discovery so the glasses get a reachable bridge URL.

The bridge binds a LAN WebSocket, but a raw LAN IP breaks the moment the phone
leaves the Wi-Fi. When Tailscale is up we prefer the tailnet MagicDNS name, which
is reachable from anywhere on the tailnet. Everything here is best-effort.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from typing import Optional

_TAILSCALE_APP_BIN = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"


def _tailscale_bin() -> Optional[str]:
    found = shutil.which("tailscale")
    if found:
        return found
    if os.path.exists(_TAILSCALE_APP_BIN):
        return _TAILSCALE_APP_BIN
    return None


def detect_tailscale() -> Optional[dict]:
    """Return ``{'ip','magic_dns','online'}`` if Tailscale is reachable, else None."""
    binary = _tailscale_bin()
    if not binary:
        return None
    try:
        r = subprocess.run([binary, "status", "--json"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0 or not (r.stdout or "").strip():
            return _detect_via_ip(binary)
        data = json.loads(r.stdout)
    except Exception:
        return _detect_via_ip(binary)
    self_ = data.get("Self") or {}
    ips = self_.get("TailscaleIPs") or []
    ip = next((a for a in ips if a.startswith("100.")), ips[0] if ips else "")
    dns = (self_.get("DNSName") or "").rstrip(".")
    if not ip and not dns:
        return None
    return {"ip": ip, "magic_dns": dns, "online": bool(self_.get("Online"))}


def _detect_via_ip(binary: str) -> Optional[dict]:
    try:
        r = subprocess.run([binary, "ip", "-4"],
                           capture_output=True, text=True, timeout=5)
        lines = (r.stdout or "").strip().splitlines() if r.returncode == 0 else []
        ip = lines[0].strip() if lines else ""
    except Exception:
        ip = ""
    if not ip:
        return None
    return {"ip": ip, "magic_dns": "", "online": True}


def lan_ip() -> str:
    """Best-effort primary non-loopback IPv4 (no traffic is actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def preferred_connect_url(cfg, ts: Optional[dict] = None) -> str:
    """The ``ws://`` URL the glasses should use: MagicDNS > Tailscale IP > LAN IP."""
    if ts is None:
        ts = detect_tailscale()
    host = ""
    if ts and cfg.net_mode in ("both", "tailnet"):
        host = ts.get("magic_dns") or ts.get("ip") or ""
    if not host:
        host = lan_ip()
    return f"ws://{host}:{cfg.ws_port}"


def bind_host(cfg, ts: Optional[dict] = None) -> str:
    """Resolve the WebSocket bind host from ``net_mode``.

    ``tailnet`` binds the Tailscale interface only (falling back to the configured
    host if no tailnet is present); ``both``/``lan`` bind the configured host
    (``0.0.0.0`` by default).
    """
    if cfg.net_mode == "tailnet":
        if ts is None:
            ts = detect_tailscale()
        if ts and ts.get("ip"):
            return ts["ip"]
    return cfg.ws_host
