import pytest as _pytest
_pytest.importorskip("gateway")  # gateway-dependent module
pytestmark = _pytest.mark.gateway

import json, asyncio, pytest
from gateway.config import PlatformConfig
from hermes_evenhub_bridge.adapter import EvenG2Adapter
from hermes_evenhub_bridge.config import BridgeConfig
from hermes_evenhub_bridge import hooks


class FakeWS:
    def __init__(self): self.sent = []
    async def send(self, d): self.sent.append(json.loads(d))


@pytest.mark.asyncio
async def test_pre_and_post_tool_emit_scoped_frames(tmp_path):
    a = EvenG2Adapter(PlatformConfig(extra={}),
                      bridge_cfg=BridgeConfig(token="t"),
                      status_path=tmp_path / "s.json")
    a._loop = asyncio.get_event_loop()
    ws = FakeWS(); a._registry.register("g2", ws)
    a._session_by_chat["g2"] = "sess1"
    hooks.bind(a)

    hooks.pre_tool_call(tool_name="Bash", args={}, task_id="", session_id="sess1", tool_call_id="c1")
    hooks.post_tool_call(tool_name="Bash", args={}, result="{}", task_id="",
                         session_id="sess1", tool_call_id="c1", duration_ms=5)
    await asyncio.sleep(0.05)
    kinds = [(m["t"], m["name"]) for m in ws.sent]
    assert ("tool.start", "Bash") in kinds
    assert ("tool.end", "Bash") in kinds


@pytest.mark.asyncio
async def test_unrelated_session_is_ignored(tmp_path):
    a = EvenG2Adapter(PlatformConfig(extra={}),
                      bridge_cfg=BridgeConfig(token="t"),
                      status_path=tmp_path / "s.json")
    a._loop = asyncio.get_event_loop()
    ws = FakeWS(); a._registry.register("g2", ws)
    a._session_by_chat["g2"] = "sess1"
    hooks.bind(a)
    hooks.pre_tool_call(tool_name="Bash", args={}, task_id="", session_id="OTHER", tool_call_id="c1")
    await asyncio.sleep(0.05)
    assert ws.sent == []
