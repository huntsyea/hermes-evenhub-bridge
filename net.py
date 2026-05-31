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


def tailscale_status() -> dict:
    """Return Tailscale CLI and node status without requiring callers to shell out."""
    binary = _tailscale_bin()
    if not binary:
        return {"installed": False, "online": False, "binary": "", "ip": "", "magic_dns": ""}
    try:
        r = subprocess.run([binary, "status", "--json"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0 or not (r.stdout or "").strip():
            via_ip = _detect_via_ip(binary)
            return {
                "installed": True,
                "online": bool(via_ip),
                "binary": binary,
                "ip": (via_ip or {}).get("ip", ""),
                "magic_dns": "",
            }
        data = json.loads(r.stdout)
    except Exception:
        via_ip = _detect_via_ip(binary)
        return {
            "installed": True,
            "online": bool(via_ip),
            "binary": binary,
            "ip": (via_ip or {}).get("ip", ""),
            "magic_dns": "",
        }
    self_ = data.get("Self") or {}
    if not self_.get("Online"):
        return {"installed": True, "online": False, "binary": binary, "ip": "", "magic_dns": ""}
    ips = self_.get("TailscaleIPs") or []
    ip = next((a for a in ips if a.startswith("100.")), ips[0] if ips else "")
    dns = (self_.get("DNSName") or "").rstrip(".")
    return {"installed": True, "online": bool(ip or dns), "binary": binary,
            "ip": ip, "magic_dns": dns}


def detect_tailscale() -> Optional[dict]:
    """Return ``{'ip','magic_dns','online'}`` if Tailscale is reachable, else None."""
    status = tailscale_status()
    if not status.get("installed") or not status.get("online"):
        # Logged out / `tailscale down`: don't advertise a stale tailnet host;
        # let the caller fall back to the LAN address.
        return None
    ip = status.get("ip", "")
    dns = status.get("magic_dns", "")
    if not ip and not dns:
        return None
    return {"ip": ip, "magic_dns": dns, "online": True}


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


def _is_pinned(cfg) -> bool:
    """True when the operator bound a specific interface (not a wildcard)."""
    return bool(cfg.ws_host) and cfg.ws_host not in ("0.0.0.0", "::")


def _fmt_host(host: str) -> str:
    # Bracket IPv6 literals so the :port stays unambiguous in a ws:// URL.
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def preferred_connect_url(cfg, ts: Optional[dict] = None) -> str:
    """The ``ws://`` URL the glasses should use.

    Host precedence is chosen to match what the bridge actually binds:
    a pinned ``EVENHUB_BRIDGE_HOST`` wins (except in ``tailnet`` mode), otherwise
    Tailscale MagicDNS > Tailscale IP (in ``both``/``tailnet``), else the LAN IP.
    ``ts`` is the already-detected info (pass ``None`` for "no Tailscale").
    """
    host = ""
    if cfg.net_mode == "tailnet" and ts:
        host = ts.get("magic_dns") or ts.get("ip") or ""
    elif _is_pinned(cfg):
        host = cfg.ws_host
    elif ts and cfg.net_mode == "both":
        host = ts.get("magic_dns") or ts.get("ip") or ""
    if not host:
        host = lan_ip()
    return f"ws://{_fmt_host(host)}:{cfg.ws_port}"


def public_connect_url(cfg, ts: Optional[dict] = None) -> str:
    """Return the configured WSS app URL."""
    if getattr(cfg, "public_url", ""):
        return cfg.public_url.rstrip("/")
    return ""


def tailscale_serve_url(cfg, ts: Optional[dict] = None) -> str:
    """Return the WSS URL Tailscale Serve would expose for this node."""
    host = (ts or {}).get("magic_dns") or ""
    if not host:
        return ""
    return f"wss://{host}:{cfg.serve_port}"


def bind_host(cfg, ts: Optional[dict] = None) -> str:
    """Resolve the WebSocket bind host from ``net_mode``.

    ``tailnet`` binds the Tailscale interface only (falling back to the configured
    host if no tailnet is present); ``both``/``lan`` bind the configured host
    (``0.0.0.0`` by default). ``ts`` is authoritative — this never probes.
    """
    if cfg.net_mode == "tailnet" and ts and ts.get("ip"):
        return ts["ip"]
    return cfg.ws_host


def resolve(cfg) -> tuple[str, str, Optional[dict]]:
    """Detect Tailscale once and return ``(bind_host, connect_url, ts)``.

    Skips Tailscale detection entirely in ``lan`` mode. Call this off the event
    loop (it shells out to the ``tailscale`` CLI).
    """
    ts = None if cfg.net_mode == "lan" else detect_tailscale()
    return bind_host(cfg, ts), preferred_connect_url(cfg, ts), ts
