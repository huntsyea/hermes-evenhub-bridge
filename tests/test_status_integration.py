import pytest as _pytest
_pytest.importorskip("gateway")  # gateway-dependent module
pytestmark = _pytest.mark.gateway

from gateway.config import PlatformConfig
from hermes_evenhub_bridge.adapter import EvenG2Adapter
from hermes_evenhub_bridge.config import BridgeConfig


def _adapter(tmp_path):
    return EvenG2Adapter(PlatformConfig(extra={}),
                         bridge_cfg=BridgeConfig(token="t"),
                         status_path=tmp_path / "s.json")


def test_refresh_status_reflects_connection_count(tmp_path):
    a = _adapter(tmp_path)

    class WS:
        async def send(self, d): pass
    a._registry.register("g2", WS())
    a.refresh_status()
    assert a._status.read()["connected"] == 1
    a._registry.unregister("g2")
    a.refresh_status()
    assert a._status.read()["connected"] == 0
