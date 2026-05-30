"""One-time self-bootstrap of the plugin's third-party Python dependencies.

Hermes installs plugins by cloning the repo into ``~/.hermes/plugins/`` and never
runs pip (``plugins_cmd.py`` only renders ``after-install.md`` as display text).
A freshly installed plugin would therefore fail to import ``websockets``/``numpy``
the moment ``register()`` pulls in the adapter. This module installs the runtime
deps into the gateway's own interpreter the first time the plugin loads, then
no-ops on every subsequent start.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

# import-name -> pip-name (they only differ for faster-whisper)
RUNTIME_MODULES = {
    "websockets": "websockets",
    "numpy": "numpy",
    "faster_whisper": "faster-whisper",
}


def _missing_modules() -> list[str]:
    missing: list[str] = []
    for import_name in RUNTIME_MODULES:
        try:
            if importlib.util.find_spec(import_name) is None:
                missing.append(import_name)
        except (ImportError, ValueError):
            missing.append(import_name)
    return missing


def _requirements_path() -> Path:
    return Path(__file__).resolve().parent / "requirements.txt"


def _marker_path(version: str) -> Path:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    return home / "even_g2" / f".deps-{version}"


def _pip_install(req: Path) -> bool:
    """Install from *req* using the gateway's interpreter.

    Tries ``python -m pip`` first, then ``python -m uv pip`` for uv/pipx-managed
    environments. Returns True if any attempt exits 0.
    """
    attempts = [
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        [sys.executable, "-m", "uv", "pip", "install", "-r", str(req)],
    ]
    for argv in attempts:
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=600)
        except Exception:
            continue
        if result.returncode == 0:
            return True
    return False


def ensure_runtime_deps(log=None, version: str = "") -> bool:
    """Ensure the runtime deps are importable. Never raises.

    Returns True when every dep in :data:`RUNTIME_MODULES` is importable (either
    already, or after a successful install). Returns False if they are still
    missing afterward (e.g. pip unavailable / offline) so the caller can register
    the platform in a disabled state.
    """
    if not _missing_modules():
        return True

    req = _requirements_path()
    if not req.exists():
        if log:
            log.error("Even G2 bridge: requirements.txt not found at %s", req)
        return False

    if log:
        log.warning("Even G2 bridge: installing missing dependencies via pip ...")
    _pip_install(req)
    importlib.invalidate_caches()

    still_missing = _missing_modules()
    if still_missing:
        if log:
            log.error(
                "Even G2 bridge: dependencies still missing after install (%s). "
                "Install them manually: %s -m pip install -r %s",
                ", ".join(still_missing), sys.executable, req,
            )
        return False

    try:  # success marker is best-effort
        marker = _marker_path(version or "x")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("ok")
    except Exception:
        pass
    if log:
        log.info("Even G2 bridge: dependencies installed.")
    return True
