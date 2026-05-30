"""Auto-download the prebuilt parakeet ASR sidecar (Swift / FluidAudio) binary.

The Swift sidecar isn't shipped inside the plugin — the ``git subtree split`` that
publishes the plugin excludes ``bridge/sidecar/``. On Apple Silicon macOS we fetch
a prebuilt binary from the plugin's GitHub Releases the first time a parakeet model
is downloaded; on every other platform the bridge stays on the whisper-tiny
fallback. Everything here is best-effort and never raises.
"""
from __future__ import annotations

import hashlib
import os
import platform
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path

RELEASE_REPO = "huntsyea/hermes-evenhub-bridge"
ASSET_NAME = "g2-asr-sidecar-macos-arm64"


def is_supported_platform() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _release_base(version: str) -> str:
    # Overridable so forks / org transfers / mirrors can redirect the asset host.
    repo = os.environ.get("EVENHUB_ASR_SIDECAR_REPO", RELEASE_REPO)
    return f"https://github.com/{repo}/releases/download/sidecar-v{version}"


def _download(url: str, timeout: float = 300.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _dequarantine(path: Path) -> None:
    # Unsigned downloads get a quarantine xattr that Gatekeeper blocks; strip it.
    try:
        subprocess.run(
            ["xattr", "-d", "com.apple.quarantine", str(path)],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def ensure_sidecar_binary(version: str, dest: str, log=None) -> str | None:
    """Ensure a runnable sidecar binary exists at *dest*, downloading if needed.

    Returns the path on success, or ``None`` when unsupported / unavailable (the
    caller then falls back to whisper). Never raises.
    """
    dest_path = Path(dest)
    if dest_path.exists() and os.access(dest_path, os.X_OK):
        return str(dest_path)
    if not is_supported_platform():
        if log:
            log.info("Even G2 bridge: sidecar auto-download skipped "
                     "(not macOS/arm64); using whisper fallback.")
        return None

    base = _release_base(version)
    try:
        blob = _download(f"{base}/{ASSET_NAME}")
        try:
            expected = _download(f"{base}/{ASSET_NAME}.sha256").decode().split()[0].strip()
        except Exception as e:  # noqa: BLE001
            # Never install/execute an unverified binary; fall back to whisper.
            if log:
                log.error("Even G2 bridge: could not fetch sidecar checksum (%s); "
                          "refusing to install unverified binary.", e)
            return None
        actual = hashlib.sha256(blob).hexdigest()
        if actual != expected:
            if log:
                log.error("Even G2 bridge: sidecar checksum mismatch "
                          "(%s != %s); not installing.", actual, expected)
            return None
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest_path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        tmp.replace(dest_path)
        _dequarantine(dest_path)
        if log:
            log.info("Even G2 bridge: downloaded sidecar to %s", dest_path)
        return str(dest_path)
    except Exception as e:  # noqa: BLE001
        if log:
            log.warning("Even G2 bridge: sidecar download failed (%s); "
                        "using whisper fallback.", e)
        return None
