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
# Apple Developer Team ID the official sidecar is signed with. The sha256 only
# protects transit (it comes from the same origin as the binary); verifying the
# Developer ID signature pins the publisher. Forks shipping their own binary set
# EVENHUB_ASR_SIDECAR_TEAM_ID to their team, or "" to disable the check.
DEVELOPER_ID_TEAM = "5J4FVDUC9M"


def is_supported_platform() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _release_base(version: str) -> str:
    # Overridable so forks / org transfers / mirrors can redirect the asset host.
    repo = os.environ.get("EVENHUB_ASR_SIDECAR_REPO", RELEASE_REPO)
    return f"https://github.com/{repo}/releases/download/sidecar-v{version}"


def _download(url: str, timeout: float = 30.0) -> bytes:
    # For small assets (the .sha256 sidecar file).
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _stream_to_file(url: str, dest_tmp: Path, timeout: float = 300.0) -> str:
    """Stream *url* into *dest_tmp* in chunks, returning the sha256 hexdigest.

    Avoids buffering the whole ~6MB binary in memory and caps a stalled transfer
    to the socket timeout per read.
    """
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=timeout) as resp, open(dest_tmp, "wb") as f:  # noqa: S310
        for chunk in iter(lambda: resp.read(65536), b""):
            h.update(chunk)
            f.write(chunk)
    return h.hexdigest()


def _verify_signature(path: Path, log=None) -> bool:
    """Verify the binary is validly signed by our Developer ID team.

    Set ``EVENHUB_ASR_SIDECAR_TEAM_ID=""`` to disable (forks shipping ad-hoc binaries).
    """
    team = os.environ.get("EVENHUB_ASR_SIDECAR_TEAM_ID", DEVELOPER_ID_TEAM)
    if not team:
        return True
    try:
        v = subprocess.run(["codesign", "--verify", "--strict", str(path)],
                           capture_output=True, text=True, timeout=30)
        if v.returncode != 0:
            if log:
                log.error("Even G2 bridge: sidecar signature invalid (%s); not installing.",
                          (v.stderr or "").strip())
            return False
        d = subprocess.run(["codesign", "-dvvv", str(path)],
                           capture_output=True, text=True, timeout=30)
        if f"TeamIdentifier={team}" not in ((d.stderr or "") + (d.stdout or "")):
            if log:
                log.error("Even G2 bridge: sidecar Team ID mismatch (expected %s); "
                          "not installing.", team)
            return False
        return True
    except Exception as e:  # noqa: BLE001
        if log:
            log.error("Even G2 bridge: sidecar signature check failed (%s); not installing.", e)
        return False


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
    tmp = dest_path.with_suffix(".tmp")
    try:
        # Fetch the (small) checksum first; refuse to install if it's unavailable.
        try:
            expected = _download(f"{base}/{ASSET_NAME}.sha256").decode().split()[0].strip()
        except Exception as e:  # noqa: BLE001
            if log:
                log.error("Even G2 bridge: could not fetch sidecar checksum (%s); "
                          "refusing to install unverified binary.", e)
            return None
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        actual = _stream_to_file(f"{base}/{ASSET_NAME}", tmp)
        if actual != expected:
            tmp.unlink(missing_ok=True)
            if log:
                log.error("Even G2 bridge: sidecar checksum mismatch "
                          "(%s != %s); not installing.", actual, expected)
            return None
        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        if not _verify_signature(tmp, log):
            tmp.unlink(missing_ok=True)
            return None
        tmp.replace(dest_path)
        _dequarantine(dest_path)
        if log:
            log.info("Even G2 bridge: downloaded sidecar to %s", dest_path)
        return str(dest_path)
    except Exception as e:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        if log:
            log.warning("Even G2 bridge: sidecar download failed (%s); "
                        "using whisper fallback.", e)
        return None
