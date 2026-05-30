"""One-time self-bootstrap of the plugin's third-party Python dependencies.

Hermes installs plugins by cloning the repo into ``~/.hermes/plugins/`` and never
runs pip (``plugins_cmd.py`` only renders ``after-install.md`` as display text).
A freshly installed plugin would therefore fail to import ``websockets``/``numpy``
the moment ``register()`` pulls in the adapter. This module installs the runtime
deps into the gateway's own interpreter the first time the plugin loads, then
no-ops on every subsequent start (the import probe is the fast path).

If an install attempt fails, a per-version cooldown marker is written so the
gateway isn't blocked for minutes on a doomed ``pip install`` on every restart;
the operator installs manually (and removes the marker) or upgrades.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

# Import names the adapter needs at load time. The pip names + pins live in
# requirements.txt (the single install source); this is only the probe list.
RUNTIME_MODULES = ("websockets", "numpy", "faster_whisper")


def _missing_modules() -> list[str]:
    missing: list[str] = []
    for name in RUNTIME_MODULES:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ImportError, ValueError):
            missing.append(name)
    return missing


def _requirements_path() -> Path:
    return Path(__file__).resolve().parent / "requirements.txt"


def _failed_marker(version: str) -> Path:
    from .config import hermes_home
    return hermes_home() / "even_g2" / f".deps-failed-{version or 'x'}"


def _pip_install(req: Path, log=None) -> bool:
    """Install from *req* using the gateway's interpreter.

    Tries ``python -m pip`` first, then the ``uv`` executable (for uv/pipx-managed
    environments that have no in-venv pip). Surfaces the failing command's stderr.
    """
    attempts = [[sys.executable, "-m", "pip", "install", "-r", str(req)]]
    uv = shutil.which("uv")
    if uv:
        attempts.append([uv, "pip", "install", "--python", sys.executable, "-r", str(req)])
    for argv in attempts:
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=600)
        except Exception as e:  # noqa: BLE001
            if log:
                log.warning("Even G2 bridge: `%s` could not run (%s)", argv[0], e)
            continue
        if result.returncode == 0:
            return True
        if log:
            log.warning("Even G2 bridge: `%s …` exited %s: %s",
                        " ".join(argv[:3]), result.returncode,
                        (result.stderr or result.stdout or "").strip()[-500:])
    return False


def ensure_runtime_deps(log=None, version: str = "") -> bool:
    """Ensure the runtime deps are importable. Never raises.

    Returns True when every dep in :data:`RUNTIME_MODULES` is importable (already,
    or after a successful install). Returns False if they are still missing — the
    caller then registers the platform disabled.
    """
    missing = _missing_modules()
    if not missing:
        return True

    marker = _failed_marker(version)
    if marker.exists():
        if log:
            log.error(
                "Even G2 bridge: dependencies missing and a previous auto-install "
                "failed. Install manually: %s -m pip install -r %s, then delete %s "
                "and restart.", sys.executable, _requirements_path(), marker)
        return False

    req = _requirements_path()
    if not req.exists():
        if log:
            log.error("Even G2 bridge: requirements.txt not found at %s", req)
        return False

    if log:
        log.warning("Even G2 bridge: installing missing dependencies (%s) — this "
                    "can take a few minutes on first run ...", ", ".join(missing))
    _pip_install(req, log)
    importlib.invalidate_caches()

    if _missing_modules():
        try:  # cooldown so we don't re-hang on every restart
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("install failed")
        except Exception:
            pass
        if log:
            log.error(
                "Even G2 bridge: dependencies still missing after install. Install "
                "manually: %s -m pip install -r %s", sys.executable, req)
        return False

    try:  # success — clear any stale cooldown marker
        marker.unlink()
    except (FileNotFoundError, OSError):
        pass
    if log:
        log.info("Even G2 bridge: dependencies installed.")
    return True
