import pytest as _pytest
_pytest.importorskip("gateway")  # gateway-dependent module
pytestmark = _pytest.mark.gateway

import pytest
from gateway.config import PlatformConfig, Platform
from hermes_evenhub_bridge.adapter import EvenG2Adapter
from hermes_evenhub_bridge.config import BridgeConfig


def _adapter(tmp_path):
    bcfg = BridgeConfig(ws_host="127.0.0.1", ws_port=0, token="secret")
    return EvenG2Adapter(PlatformConfig(extra={}), bridge_cfg=bcfg,
                         status_path=tmp_path / "s.json")


def test_platform_identity(tmp_path):
    a = _adapter(tmp_path)
    assert a.platform == Platform("even_g2")
    assert a.name == "Even_G2"


@pytest.mark.asyncio
async def test_connect_starts_server_and_marks_connected(tmp_path):
    a = _adapter(tmp_path)
    ok = await a.connect()
    try:
        assert ok is True
        assert a._running is True
        assert a.bound_port > 0
    finally:
        await a.disconnect()
    assert a._running is False


@pytest.mark.asyncio
async def test_get_chat_info(tmp_path):
    a = _adapter(tmp_path)
    info = await a.get_chat_info("g2")
    assert info == {"name": "g2", "type": "dm"}
