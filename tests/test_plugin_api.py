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
