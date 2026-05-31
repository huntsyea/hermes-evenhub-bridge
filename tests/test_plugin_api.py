import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_router(monkeypatch, tmp_path):
    # Point the status + config at temp locations.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location(
        "g2_plugin_api",
        Path(__file__).parent.parent / "dashboard/plugin_api.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plugin_api_imports_when_loaded_standalone(tmp_path):
    plugin_api = Path(__file__).parent.parent / "dashboard/plugin_api.py"
    code = f"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("g2_plugin_api_standalone", {str(plugin_api)!r})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert mod.router is not None
"""
    env = {**os.environ, "HERMES_HOME": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_status_endpoint_reads_status_file(monkeypatch, tmp_path):
    from hermes_evenhub_bridge.status import StatusFile
    StatusFile(tmp_path / "even_g2_status.json").update(connected=2, mic="idle")
    mod = _load_router(monkeypatch, tmp_path)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    r = client.get("/api/plugins/g2/status")
    assert r.status_code == 200
    assert r.json()["connected"] == 2


def test_setup_status_endpoint_does_not_return_token(monkeypatch, tmp_path):
    monkeypatch.setenv("EVENHUB_BRIDGE_TOKEN", "secret-token")
    mod = _load_router(monkeypatch, tmp_path)
    monkeypatch.setattr(mod.setup_flow, "setup_status", lambda: {
        "token_configured": True,
        "public_url": "wss://host.ts.net:8443",
    })
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    body = client.get("/api/plugins/g2/setup/status").json()
    assert body["token_configured"] is True
    assert "secret-token" not in str(body)


def test_setup_local_endpoint_returns_generated_token(monkeypatch, tmp_path):
    mod = _load_router(monkeypatch, tmp_path)
    monkeypatch.setattr(mod.setup_flow, "configure_local_bridge", lambda force_token=False: {
        "ok": True,
        "token_generated": True,
        "token_replaced": force_token,
        "token": "new-token",
    })
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    body = client.post("/api/plugins/g2/setup/local").json()
    assert body["token"] == "new-token"
    assert body["token_replaced"] is False


def test_setup_local_endpoint_accepts_force_token(monkeypatch, tmp_path):
    mod = _load_router(monkeypatch, tmp_path)
    calls = []

    def configure_local_bridge(force_token=False):
        calls.append(force_token)
        return {
            "ok": True,
            "token_generated": True,
            "token_replaced": force_token,
            "token": "replacement-token",
        }

    monkeypatch.setattr(mod.setup_flow, "configure_local_bridge", configure_local_bridge)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    body = client.post("/api/plugins/g2/setup/local", json={"force_token": True}).json()
    assert calls == [True]
    assert body["token"] == "replacement-token"
    assert body["token_replaced"] is True


def test_tailscale_serve_endpoint_maps_setup_error(monkeypatch, tmp_path):
    mod = _load_router(monkeypatch, tmp_path)

    def fail(serve_port=None):
        raise mod.setup_flow.SetupError("tailscale is installed but not online")

    monkeypatch.setattr(mod.setup_flow, "enable_tailscale_serve", fail)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    r = client.post("/api/plugins/g2/setup/tailscale-serve", json={"serve_port": 9443})
    assert r.status_code == 400
    assert "not online" in r.json()["detail"]


@pytest.mark.gateway  # config endpoints import hermes_cli (part of the Hermes install)
def test_config_roundtrip(monkeypatch, tmp_path):
    pytest.importorskip("hermes_cli.config")
    mod = _load_router(monkeypatch, tmp_path)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    r = client.post("/api/plugins/g2/config",
                    json={"ws_host": "0.0.0.0", "ws_port": 8770})
    assert r.status_code == 200
    got = client.get("/api/plugins/g2/config").json()
    assert got["ws_port"] == 8770
    assert "asr_model" not in got


@pytest.mark.gateway  # config endpoints import hermes_cli (part of the Hermes install)
def test_config_port_out_of_range_falls_back_to_default(monkeypatch, tmp_path):
    pytest.importorskip("hermes_cli.config")
    mod = _load_router(monkeypatch, tmp_path)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    r = client.post("/api/plugins/g2/config",
                    json={"ws_host": "0.0.0.0", "ws_port": 99999})
    assert r.status_code == 200
    assert r.json()["ws_port"] == 8765
    assert client.get("/api/plugins/g2/config").json()["ws_port"] == 8765


def test_get_asr_models(monkeypatch, tmp_path):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    mod = _load_router(monkeypatch, tmp_path)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    r = client.get("/api/plugins/g2/asr/models")
    assert r.status_code == 200
    names = {m["name"] for m in r.json()["models"]}
    assert {"parakeet-tdt-0.6b-v2", "whisper-tiny"} <= names


def test_get_asr_models_does_not_run_sidecar_check(monkeypatch, tmp_path):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    mod = _load_router(monkeypatch, tmp_path)
    calls = []

    def fake_build(name, cfg):
        calls.append(name)
        if name.startswith("parakeet"):
            raise AssertionError("sidecar status must not launch model checks")

        class Backend:
            def is_installed(self):
                return False

        return Backend()

    monkeypatch.setattr(mod.asr_pkg, "_build_backend", fake_build)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    r = client.get("/api/plugins/g2/asr/models")
    assert r.status_code == 200
    assert all("parakeet" not in name for name in calls)
    assert any("parakeet" not in name for name in calls)


def test_get_asr_models_reports_sidecar_binary(monkeypatch, tmp_path):
    sidecar = tmp_path / "bin" / "g2-asr-sidecar"
    sidecar.parent.mkdir()
    sidecar.write_bytes(b"x")
    sidecar.chmod(0o755)
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    monkeypatch.setenv("EVENHUB_ASR_SIDECAR_BIN", str(sidecar))
    mod = _load_router(monkeypatch, tmp_path)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    body = client.get("/api/plugins/g2/asr/models").json()
    assert body["sidecar"]["path"] == str(sidecar)
    assert body["sidecar"]["installed"] is True
    parakeet = next(m for m in body["models"] if m["name"] == "parakeet-tdt-0.6b-v2")
    assert parakeet["installed"] is False
    assert parakeet["downloadable"] is True
    assert parakeet["sidecar_installed"] is True
    assert parakeet["active"] is True


def test_set_active_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    mod = _load_router(monkeypatch, tmp_path)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    assert client.post("/api/plugins/g2/asr/set/whisper-tiny").status_code == 200
    active = next(m for m in client.get("/api/plugins/g2/asr/models").json()["models"] if m["active"])
    assert active["name"] == "whisper-tiny"


def test_set_unknown_is_400(monkeypatch, tmp_path):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    mod = _load_router(monkeypatch, tmp_path)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    assert client.post("/api/plugins/g2/asr/set/bogus").status_code == 400


def test_download_failure_is_non_2xx(monkeypatch, tmp_path):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    mod = _load_router(monkeypatch, tmp_path)

    class Backend:
        def ensure_downloaded(self):
            raise RuntimeError("sidecar missing")

    monkeypatch.setattr(mod.asr_pkg, "_build_backend", lambda name, cfg: Backend())
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    r = client.post("/api/plugins/g2/asr/download/parakeet-tdt-0.6b-v2")
    assert r.status_code == 500
    assert r.json()["detail"] == "sidecar missing"
