"""One-click setup helpers for the private WSS bridge path.

The bridge still speaks local plain WebSocket. Setup makes that local socket
reachable to the Even companion app through user-owned Tailscale Serve.
"""
from __future__ import annotations

import os
import secrets
import subprocess
from typing import Callable

from . import net
from .config import BridgeConfig, parse_serve_port, hermes_home

_LOCAL_HOST = "127.0.0.1"
_ENV_TOKEN = "EVENHUB_BRIDGE_TOKEN"
_ENV_HOST = "EVENHUB_BRIDGE_HOST"
_ENV_NET = "EVENHUB_BRIDGE_NET"
_ENV_PORT = "EVENHUB_BRIDGE_PORT"
_ENV_PUBLIC_URL = "EVENHUB_BRIDGE_PUBLIC_URL"
_ENV_SERVE_PORT = "EVENHUB_BRIDGE_SERVE_PORT"


class SetupError(RuntimeError):
    """Raised when setup cannot safely complete without user action."""


def _save_env_value(key: str, value: str) -> None:
    os.environ[key] = value
    try:
        from hermes_cli.config import save_env_value
        save_env_value(key, value)
        return
    except Exception:
        pass
    env_path = hermes_home() / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    prefix = f"{key}="
    entry = f"{key}={value}"
    replaced = False
    for idx, line in enumerate(lines):
        if line.startswith(prefix):
            lines[idx] = entry
            replaced = True
            break
    if not replaced:
        lines.append(entry)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(env_path, 0o600)


def local_bridge_url(cfg: BridgeConfig) -> str:
    return f"ws://{_LOCAL_HOST}:{cfg.ws_port}"


def build_serve_command(cfg: BridgeConfig, serve_port: int | None = None) -> list[str]:
    binary = net._tailscale_bin()
    if not binary:
        raise SetupError("tailscale CLI not found")
    https_port = parse_serve_port(serve_port if serve_port is not None else cfg.serve_port)
    return [
        binary,
        "serve",
        f"--https={https_port}",
        "--bg",
        f"http://{_LOCAL_HOST}:{cfg.ws_port}",
    ]


def setup_status(cfg: BridgeConfig | None = None) -> dict:
    cfg = cfg or BridgeConfig.from_env()
    ts = net.tailscale_status()
    derived = None
    if ts.get("online") and ts.get("magic_dns"):
        derived = {"magic_dns": ts["magic_dns"], "ip": ts.get("ip", ""), "online": True}
    public_url = net.public_connect_url(cfg, derived)
    candidate_public_url = net.tailscale_serve_url(cfg, derived)
    return {
        "token_configured": bool(cfg.token),
        "local_url": local_bridge_url(cfg),
        "configured_host": cfg.ws_host,
        "configured_port": cfg.ws_port,
        "configured_net_mode": cfg.net_mode,
        "loopback_recommended": cfg.ws_host == _LOCAL_HOST and cfg.net_mode == "lan",
        "restart_required_for_config": cfg.ws_host != _LOCAL_HOST or cfg.net_mode != "lan",
        "public_url": public_url,
        "candidate_public_url": candidate_public_url,
        "serve_port": cfg.serve_port,
        "tailscale": ts,
    }


def configure_local_bridge(
    *,
    cfg: BridgeConfig | None = None,
    force_token: bool = False,
    token_factory: Callable[[], str] | None = None,
) -> dict:
    cfg = cfg or BridgeConfig.from_env()
    token = cfg.token
    generated_token = ""
    if force_token or not token:
        generated_token = (token_factory or (lambda: secrets.token_urlsafe(32)))()
        _save_env_value(_ENV_TOKEN, generated_token)
    token_replaced = bool(token and generated_token)

    _save_env_value(_ENV_HOST, _LOCAL_HOST)
    _save_env_value(_ENV_NET, "lan")
    _save_env_value(_ENV_PORT, str(cfg.ws_port))
    return {
        "ok": True,
        "token_generated": bool(generated_token),
        "token_replaced": token_replaced,
        "token": generated_token,
        "restart_required": cfg.ws_host != _LOCAL_HOST or cfg.net_mode != "lan" or bool(generated_token),
        "local_url": local_bridge_url(cfg),
    }


def enable_tailscale_serve(
    *,
    cfg: BridgeConfig | None = None,
    serve_port: int | None = None,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> dict:
    cfg = cfg or BridgeConfig.from_env()
    ts = net.tailscale_status()
    if not ts.get("installed"):
        raise SetupError("tailscale CLI not found")
    if not ts.get("online"):
        raise SetupError("tailscale is installed but not online")
    if not ts.get("magic_dns"):
        raise SetupError("tailscale MagicDNS name is unavailable")

    https_port = parse_serve_port(serve_port if serve_port is not None else cfg.serve_port)
    command = build_serve_command(cfg, https_port)
    run = runner or subprocess.run
    result = run(command, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "tailscale serve failed").strip()
        raise SetupError(detail)

    public_url = f"wss://{ts['magic_dns']}:{https_port}"
    _save_env_value(_ENV_PUBLIC_URL, public_url)
    _save_env_value(_ENV_SERVE_PORT, str(https_port))
    return {
        "ok": True,
        "public_url": public_url,
        "local_url": local_bridge_url(cfg),
        "serve_port": https_port,
        "command": command,
    }
