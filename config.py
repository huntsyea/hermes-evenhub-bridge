import os
from dataclasses import dataclass
from pathlib import Path

_NET_MODES = ("both", "tailnet", "lan")
DEFAULT_WS_PORT = 8765
_MAX_PORT = 65535


def hermes_home() -> Path:
    """Hermes home dir — the single source of truth shared with status/bootstrap.

    Prefer the gateway's canonical, profile-aware resolver; fall back to the env
    var for standalone CLI / test use where the gateway isn't importable.
    """
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def default_sidecar_bin() -> str:
    """Absolute cache path for the auto-downloaded sidecar binary.

    The old repo-relative default (``sidecar/.build/release/...``) only resolved
    when run from the source tree; an installed plugin needs a stable location.
    """
    return str(hermes_home() / "even_g2" / "bin" / "g2-asr-sidecar")


def parse_ws_port(value: object | None) -> int:
    raw = str(DEFAULT_WS_PORT) if value is None or value == "" else value
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_WS_PORT
    if 0 <= port <= _MAX_PORT:
        return port
    return DEFAULT_WS_PORT


@dataclass
class BridgeConfig:
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    token: str = ""
    asr_sidecar_bin: str = ""
    asr_state_path: str = ""
    net_mode: str = "both"

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        net = (os.environ.get("EVENHUB_BRIDGE_NET", "both") or "both").strip().lower()
        if net not in _NET_MODES:
            net = "both"
        return cls(
            ws_host=os.environ.get("EVENHUB_BRIDGE_HOST", "0.0.0.0"),
            ws_port=parse_ws_port(os.environ.get("EVENHUB_BRIDGE_PORT")),
            token=os.environ.get("EVENHUB_BRIDGE_TOKEN", ""),
            asr_sidecar_bin=os.environ.get("EVENHUB_ASR_SIDECAR_BIN", default_sidecar_bin()),
            asr_state_path=os.environ.get(
                "EVENHUB_ASR_STATE",
                str(hermes_home() / "even_g2_asr.json")),
            net_mode=net,
        )
