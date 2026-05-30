import sys
from pathlib import Path
import pytest
from hermes_evenhub_bridge.asr import ASRUnavailable
from hermes_evenhub_bridge.asr.fluidaudio import FluidAudioBackend

STUB = Path(__file__).parent / "fixtures" / "stub_sidecar.py"


def _backend(mode="ok", timeout=5.0):
    # launch_cmd lets tests run the stub instead of a Swift binary.
    return FluidAudioBackend(
        binary_path=str(STUB),
        model_version="v2",
        timeout=timeout,
        launch_cmd=[sys.executable, str(STUB), "--mode", mode],
    )


def test_transcribe_returns_stub_text():
    b = _backend()
    try:
        assert b.transcribe(b"\x01\x02\x03") == "stub:3"
    finally:
        b.close()


def test_process_reused_across_calls():
    b = _backend()
    try:
        b.transcribe(b"\x01\x02")
        pid1 = b._proc.pid
        b.transcribe(b"\x01\x02")
        assert b._proc.pid == pid1
    finally:
        b.close()


def test_error_frame_raises_unavailable():
    b = _backend(mode="error")
    try:
        with pytest.raises(ASRUnavailable):
            b.transcribe(b"\x01\x02")
    finally:
        b.close()


def test_crash_raises_then_restarts():
    b = _backend(mode="crash")
    try:
        b.transcribe(b"\x01\x02")            # first ok
        with pytest.raises(ASRUnavailable):  # second crashes
            b.transcribe(b"\x01\x02")
        # bounded restart: a later call spins a fresh process and works
        assert b.transcribe(b"\x01\x02") == "stub:2"
    finally:
        b.close()


def test_timeout_raises_unavailable():
    b = _backend(mode="hang", timeout=0.5)
    try:
        with pytest.raises(ASRUnavailable):
            b.transcribe(b"\x01\x02")
    finally:
        b.close()


def test_missing_binary_is_not_installed_and_raises_without_launch():
    b = FluidAudioBackend(binary_path="/no/such/bin", model_version="v2", timeout=1.0)
    assert b.is_installed() is False
    with pytest.raises(ASRUnavailable):
        b.transcribe(b"\x01\x02")


def test_restart_cap_trips_after_repeated_failures():
    b = FluidAudioBackend(
        binary_path=str(STUB),
        model_version="v2",
        timeout=2.0,
        launch_cmd=[sys.executable, str(STUB), "--mode", "nostart"],
    )
    try:
        last = None
        for _ in range(6):
            try:
                b.transcribe(b"\x01\x02")
            except ASRUnavailable as e:
                last = str(e)
        assert last is not None
        assert "restart limit reached" in last
    finally:
        b.close()


def test_restart_cap_recovers_after_cooldown(monkeypatch):
    b = FluidAudioBackend(
        binary_path=str(STUB),
        model_version="v2",
        timeout=2.0,
        launch_cmd=[sys.executable, str(STUB), "--mode", "nostart"],
    )
    b._restart_window = 10.0
    clock = {"t": 1000.0}
    monkeypatch.setattr(
        "hermes_evenhub_bridge.asr.fluidaudio.time.monotonic",
        lambda: clock["t"],
    )
    try:
        # Exhaust the budget within the window.
        for _ in range(5):
            try:
                b.transcribe(b"\x01")
            except ASRUnavailable:
                pass
        # Now we should be capped.
        with pytest.raises(ASRUnavailable) as ei:
            b.transcribe(b"\x01")
        assert "restart limit reached" in str(ei.value)
        # Advance the clock past the window -> budget refills -> it tries to start again,
        # so the error is the start/handshake failure, NOT the cap message.
        clock["t"] += 20.0
        with pytest.raises(ASRUnavailable) as ei2:
            b.transcribe(b"\x01")
        assert "restart limit reached" not in str(ei2.value)
    finally:
        b.close()
