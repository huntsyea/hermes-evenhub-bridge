"""Dashboard backend for the Even G2 plugin. Mounted at
/api/plugins/hermes-evenhub-bridge/. Reads device status from the status file
and stores non-secret connection/voice settings in config.yaml under the
``even_g2`` block."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from hermes_evenhub_bridge.status import StatusFile

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
