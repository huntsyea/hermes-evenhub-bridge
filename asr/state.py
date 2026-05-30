"""Persisted active-model selection (cross-process seam, like status.py)."""
from __future__ import annotations

import json
from pathlib import Path


def set_active(name: str, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"active": name}))


def get_active(path: str | Path) -> str | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text()).get("active")
    except Exception:
        return None
