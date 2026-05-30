"""Parakeet ASR via a resident Swift (FluidAudio) sidecar over framed stdio."""
from __future__ import annotations

import json
import logging
import subprocess
import threading
from pathlib import Path

from . import ASRUnavailable
from .ipc import encode_frame, read_frame

log = logging.getLogger("hermes-evenhub-bridge")

_MAX_RESTARTS = 3


class FluidAudioBackend:
    def __init__(
        self,
        binary_path: str,
        model_version: str = "v2",
        timeout: float = 30.0,
        launch_cmd: list[str] | None = None,
        download_args: list[str] | None = None,
    ) -> None:
        self._binary = binary_path
        self._version = model_version
        self._timeout = timeout
        self._launch_cmd = launch_cmd or [binary_path, "--model-version", model_version]
        self._download_args = download_args or ["--download", "--model-version", model_version]
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._restarts = 0

    # --- lifecycle -------------------------------------------------------
    def is_installed(self) -> bool:
        if not Path(self._binary).exists():
            return False
        try:
            r = subprocess.run(
                [self._binary, "--check", "--model-version", self._version],
                timeout=self._timeout,
            )
            return r.returncode == 0
        except Exception:
            return False

    def ensure_downloaded(self) -> None:
        if not Path(self._binary).exists():
            raise ASRUnavailable("sidecar binary not built")
        r = subprocess.run([self._binary, *self._download_args], timeout=600)
        if r.returncode != 0:
            raise ASRUnavailable(f"model download failed (exit {r.returncode})")

    def _start(self) -> None:
        if not Path(self._binary).exists() and self._launch_cmd[0] == self._binary:
            raise ASRUnavailable("sidecar binary not built")
        self._proc = subprocess.Popen(
            self._launch_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        hello = json.loads(self._read_frame_timed())
        if not hello.get("ready"):
            raise ASRUnavailable(f"sidecar handshake failed: {hello}")

    def _kill(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def close(self) -> None:
        with self._lock:
            self._kill()

    # --- transcription ---------------------------------------------------
    def _read_frame_timed(self) -> bytes:
        # subprocess pipes are blocking; enforce timeout via a watchdog thread.
        result: dict = {}

        def _worker():
            try:
                result["data"] = read_frame(self._proc.stdout)
            except Exception as e:  # noqa: BLE001
                result["err"] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(self._timeout)
        if t.is_alive():
            raise ASRUnavailable("sidecar timed out")
        if "err" in result:
            raise ASRUnavailable(f"sidecar read error: {result['err']}")
        return result["data"]

    def transcribe(self, pcm: bytes) -> str:
        if not pcm:
            return ""
        with self._lock:
            try:
                if self._proc is None or self._proc.poll() is not None:
                    if self._restarts >= _MAX_RESTARTS:
                        raise ASRUnavailable("sidecar restart limit reached")
                    self._restarts += 1
                    self._start()
                self._proc.stdin.write(encode_frame(pcm))
                self._proc.stdin.flush()
                resp = json.loads(self._read_frame_timed())
            except ASRUnavailable:
                self._kill()
                raise
            except Exception as e:  # broken pipe, crash mid-write, bad json
                self._kill()
                raise ASRUnavailable(f"sidecar failure: {e}") from e
            if "error" in resp:
                # Per-request error (e.g. bad audio); the sidecar stays warm.
                raise ASRUnavailable(resp["error"])
            # A clean response means the sidecar is healthy again.
            self._restarts = 0
            return (resp.get("text") or "").strip()
