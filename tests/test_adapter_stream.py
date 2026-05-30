import pytest as _pytest
_pytest.importorskip("gateway")  # gateway-dependent module
pytestmark = _pytest.mark.gateway

import json, pytest
from gateway.config import PlatformConfig
from hermes_evenhub_bridge.adapter import EvenG2Adapter
from hermes_evenhub_bridge.config import BridgeConfig


class FakeWS:
    def __init__(self): self.sent = []
    async def send(self, d): self.sent.append(json.loads(d))


def _adapter(tmp_path):
    a = EvenG2Adapter(PlatformConfig(extra={}),
                      bridge_cfg=BridgeConfig(token="t"),
                      status_path=tmp_path / "s.json")
    return a


@pytest.mark.asyncio
async def test_send_then_edits_emit_deltas(tmp_path):
    a = _adapter(tmp_path)
    ws = FakeWS()
    a._registry.register("g2", ws)
    r1 = await a.send("g2", "hello")
    assert r1.success is True
    r2 = await a.edit_message("g2", r1.message_id, "hello world")
    assert r2.success is True
    await a.edit_message("g2", r1.message_id, "hello world!", finalize=True)
    deltas = [m["text"] for m in ws.sent if m["t"] == "assistant.delta"]
    assert deltas == ["hello", " world", "!"]


@pytest.mark.asyncio
async def test_new_send_starts_new_segment(tmp_path):
    a = _adapter(tmp_path)
    ws = FakeWS()
    a._registry.register("g2", ws)
    await a.send("g2", "first")
    await a.send("g2", "second")   # new message after a tool boundary
    deltas = [m["text"] for m in ws.sent if m["t"] == "assistant.delta"]
    assert deltas == ["first", "second"]
