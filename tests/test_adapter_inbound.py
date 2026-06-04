import pytest as _pytest
_pytest.importorskip("gateway")  # gateway-dependent module
pytestmark = _pytest.mark.gateway

import asyncio, json, pytest
from gateway.config import PlatformConfig
from gateway.session import SessionEntry
from gateway.platforms.base import MessageEvent
from hermes_evenhub_bridge.adapter import EvenG2Adapter
from hermes_evenhub_bridge.config import BridgeConfig
from datetime import datetime


class FakeWS:
    def __init__(self): self.sent = []
    async def send(self, d): self.sent.append(json.loads(d))


class FakeStore:
    def list_sessions(self, active_minutes=None):
        return [self.get_or_create_session(None)]

    def get_or_create_session(self, source, force_new=False):
        return SessionEntry(session_key="k1", session_id="sess1",
                            created_at=datetime.now(), updated_at=datetime.now(),
                            display_name="One")


def _adapter(tmp_path):
    a = EvenG2Adapter(PlatformConfig(extra={}),
                      bridge_cfg=BridgeConfig(token="t"),
                      status_path=tmp_path / "s.json")
    a.set_session_store(FakeStore())
    a._idle_poll_seconds = 0.01  # speed up the guard wait in tests
    return a


@pytest.mark.asyncio
async def test_on_text_dispatches_and_emits_turn_done(tmp_path, monkeypatch):
    a = _adapter(tmp_path)
    ws = FakeWS()
    a._registry.register("g2", ws)
    captured = {}

    async def fake_handle(event: MessageEvent):
        captured["text"] = event.text
        captured["platform"] = event.source.platform.value
        # Simulate the gateway's per-turn guard under the REAL computed key.
        key = a._session_key_for(event.source)
        a._active_sessions[key] = asyncio.Event()
        async def clear():
            await asyncio.sleep(0.05)
            a._active_sessions.pop(key, None)
        asyncio.create_task(clear())

    monkeypatch.setattr(a, "handle_message", fake_handle)
    await a.on_text("g2", "hello agent")
    # turn.done arrives after the guard clears
    for _ in range(200):
        if any(m["t"] == "turn.done" for m in ws.sent):
            break
        await asyncio.sleep(0.01)
    assert captured["text"] == "hello agent"
    assert captured["platform"] == "even_g2"
    assert a._session_by_chat["g2"] == "sess1"
    assert any(m["t"] == "turn.done" for m in ws.sent)


@pytest.mark.asyncio
async def test_rapid_second_turn_replaces_poller_single_done(tmp_path, monkeypatch):
    a = _adapter(tmp_path)
    ws = FakeWS()
    a._registry.register("g2", ws)

    # Derive the session key the same way _session_key_for does so we set the
    # guard under the exact key the poller watches.
    source = a._source_for("g2")
    session_key = a._session_key_for(source)

    async def fake_handle(event):
        a._active_sessions[session_key] = asyncio.Event()
        async def clear():
            await asyncio.sleep(0.05)
            a._active_sessions.pop(session_key, None)
        asyncio.create_task(clear())

    monkeypatch.setattr(a, "handle_message", fake_handle)
    await a.on_text("g2", "first")
    p1 = a._poller_tasks["g2"]
    await a.on_text("g2", "second")     # must replace (and cancel) the stale poller
    assert a._poller_tasks["g2"] is not p1
    await asyncio.sleep(0.4)
    done = [m for m in ws.sent if m["t"] == "turn.done"]
    assert len(done) == 1               # exactly one turn.done, not duplicated
