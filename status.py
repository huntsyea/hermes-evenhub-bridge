"""Device-level status the adapter writes (gateway process) and the dashboard
backend reads (web_server process). Cross-process via a small JSON file because
``gateway.status.write_runtime_status`` has a fixed schema."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


def default_status_path() -> Path:
    from .config import hermes_home
    return hermes_home() / "even_g2_status.json"


_DEFAULTS: Dict[str, Any] = {
    "connected": 0,
    "mic": "off",
    "active_session": "",
    "connect_url": "",
    "public_url": "",
    "local_url": "",
    "serve_port": 8443,
    "tailscale_dns": "",
    "tailscale_ip": "",
    "net_mode": "both",
    "updated_at": 0.0,
}


class StatusFile:
    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path else default_status_path()

    def update(self, **fields: Any) -> None:
        data = self.read()
        data.update(fields)
        data["updated_at"] = time.time()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(self._path)

    def read(self) -> Dict[str, Any]:
        try:
            data = json.loads(self._path.read_text())
        except (FileNotFoundError, ValueError):
            return dict(_DEFAULTS)
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
