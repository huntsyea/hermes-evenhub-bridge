"""Dashboard backend for the Even G2 plugin. Mounted at
/api/plugins/hermes-evenhub-bridge/. Reads device status from the status file
and stores non-secret connection/voice settings in config.yaml under the
``even_g2`` block."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hermes_evenhub_bridge.status import StatusFile
from hermes_evenhub_bridge.config import BridgeConfig
from hermes_evenhub_bridge import asr as asr_pkg
from hermes_evenhub_bridge.asr import REGISTRY
from hermes_evenhub_bridge.asr.state import get_active, set_active

router = APIRouter()
_CONFIG_SECTION = "even_g2"
_DEFAULT_CONFIG = {"ws_host": "0.0.0.0", "ws_port": 8765, "asr_model": "base"}


class G2Config(BaseModel):
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    asr_model: str = "base"


@router.get("/status")
async def get_status():
    return StatusFile().read()


@router.get("/config")
async def get_config():
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
    except Exception:
        cfg = {}
    section = {**_DEFAULT_CONFIG, **(cfg.get(_CONFIG_SECTION) or {})}
    return section


@router.post("/config")
async def set_config(body: G2Config):
    from hermes_cli.config import load_config, save_config
    cfg = load_config()
    cfg[_CONFIG_SECTION] = body.model_dump()
    save_config(cfg)
    return {"ok": True, **body.model_dump()}


@router.get("/asr/models")
def asr_models():
    cfg = BridgeConfig.from_env()
    active = get_active(cfg.asr_state_path) or asr_pkg.DEFAULT_ACTIVE
    models = []
    for name, spec in REGISTRY.items():
        try:
            installed = asr_pkg._build_backend(name, cfg).is_installed()
        except Exception:
            installed = False
        models.append({"name": name, "backend": spec.backend,
                       "lang": spec.lang, "installed": installed,
                       "active": name == active})
    return {"models": models, "active": active}


@router.post("/asr/set/{name}")
def asr_set(name: str):
    if name not in REGISTRY:
        raise HTTPException(status_code=400, detail="unknown model")
    set_active(name, BridgeConfig.from_env().asr_state_path)
    return {"active": name}


@router.post("/asr/download/{name}")
def asr_download(name: str):
    if name not in REGISTRY:
        raise HTTPException(status_code=400, detail="unknown model")
    cfg = BridgeConfig.from_env()
    try:
        asr_pkg._build_backend(name, cfg).ensure_downloaded()
        return {"status": "installed"}
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "detail": str(e)}
