import importlib.util
from pathlib import Path

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


def test_status_endpoint_reads_status_file(monkeypatch, tmp_path):
    from hermes_evenhub_bridge.status import StatusFile
    StatusFile(tmp_path / "even_g2_status.json").update(connected=2, mic="idle")
    mod = _load_router(monkeypatch, tmp_path)
    app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/g2")
    client = TestClient(app)
    r = client.get("/api/plugins/g2/status")
    assert r.status_code == 200
    assert r.json()["connected"] == 2


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
    assert calls == ["whisper-tiny"]


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
    assert parakeet["installed"] is True
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
