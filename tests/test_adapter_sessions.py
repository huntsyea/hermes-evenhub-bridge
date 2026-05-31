import pytest as _pytest
_pytest.importorskip("gateway")  # gateway-dependent module
pytestmark = _pytest.mark.gateway

import json, os, pytest
from datetime import datetime
from gateway.config import PlatformConfig
from gateway.session import SessionEntry
from hermes_evenhub_bridge.adapter import EvenG2Adapter
from hermes_evenhub_bridge.config import BridgeConfig


class FakeWS:
    def __init__(self): self.sent = []
    async def send(self, d): self.sent.append(json.loads(d))


class FakeDB:
    def __init__(self, messages=None):
        self.messages = messages or {}

    def get_messages(self, session_id):
        value = self.messages.get(session_id, [])
        if isinstance(value, Exception):
            raise value
        return value


def _entry(sid, name, inp, out):
    return SessionEntry(session_key="k", session_id=sid,
                        created_at=datetime.now(), updated_at=datetime.now(),
                        display_name=name, input_tokens=inp, output_tokens=out)


class FakeStore:
    def __init__(self, messages=None):
        self.switched = None
        self._db = FakeDB(messages)

    def list_sessions(self, active_minutes=None):
        return [_entry("s1", "One", 2, 3), _entry("s2", "Two", 0, 0)]
    def switch_session(self, session_key, target_session_id):
        self.switched = (session_key, target_session_id)
        return _entry(target_session_id, "Switched", 0, 0)


def _adapter(tmp_path):
    a = EvenG2Adapter(PlatformConfig(extra={}),
                      bridge_cfg=BridgeConfig(token="t"),
                      status_path=tmp_path / "s.json")
    a.set_session_store(FakeStore())
    return a


@pytest.mark.asyncio
async def test_sessions_list_maps_entries(tmp_path):
    a = _adapter(tmp_path)
    ws = FakeWS(); a._registry.register("g2", ws)
    await a.on_sessions_list("g2")
    frame = next(m for m in ws.sent if m["t"] == "sessions")
    ids = [it["id"] for it in frame["items"]]
    assert ids == ["s1", "s2"]
    one = frame["items"][0]
    assert one["title"] == "One" and one["tokens"] == 5


@pytest.mark.asyncio
async def test_sessions_switch_calls_store_and_acks(tmp_path):
    a = _adapter(tmp_path)
    ws = FakeWS(); a._registry.register("g2", ws)
    await a.on_sessions_switch("g2", "s2")
    assert a._session_store.switched[1] == "s2"
    assert any(m["t"] == "active" and m["id"] == "s2" for m in ws.sent)
    assert a._session_by_chat["g2"] == "s2"


@pytest.mark.asyncio
async def test_sessions_switch_sends_stored_history(tmp_path):
    a = _adapter(tmp_path)
    a.set_session_store(FakeStore({
        "s2": [
            {"role": "system", "content": "ignore"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": [{"type": "text", "text": "reply"}]},
            {"role": "tool", "content": "skip"},
            {"role": "assistant", "content": ""},
        ],
    }))
    ws = FakeWS(); a._registry.register("g2", ws)

    await a.on_sessions_switch("g2", "s2")

    assert [m["t"] for m in ws.sent] == ["active", "history"]
    assert ws.sent[1]["id"] == "s2"
    assert ws.sent[1]["ok"] is True
    assert ws.sent[1]["items"] == [
        {"kind": "user", "text": "first"},
        {"kind": "assistant", "text": "reply"},
    ]


@pytest.mark.asyncio
async def test_sessions_switch_reports_history_load_failure(tmp_path):
    a = _adapter(tmp_path)
    a.set_session_store(FakeStore({"s2": RuntimeError("db unavailable")}))
    ws = FakeWS(); a._registry.register("g2", ws)

    await a.on_sessions_switch("g2", "s2")

    assert ws.sent[-1] == {"t": "history", "id": "s2", "items": [], "ok": False}


def test_ensure_home_channel_sets_and_persists(tmp_path, monkeypatch):
    monkeypatch.delenv("EVEN_G2_HOME_CHANNEL", raising=False)
    calls = []
    import hermes_cli.config as cfgmod
    monkeypatch.setattr(cfgmod, "save_env_value", lambda k, v: calls.append((k, v)))
    a = _adapter(tmp_path)
    a._ensure_home_channel("g2")
    assert os.environ["EVEN_G2_HOME_CHANNEL"] == "g2"
    assert calls == [("EVEN_G2_HOME_CHANNEL", "g2")]


def test_ensure_home_channel_noop_when_already_set(tmp_path, monkeypatch):
    monkeypatch.setenv("EVEN_G2_HOME_CHANNEL", "existing")
    calls = []
    import hermes_cli.config as cfgmod
    monkeypatch.setattr(cfgmod, "save_env_value", lambda k, v: calls.append((k, v)))
    a = _adapter(tmp_path)
    a._ensure_home_channel("g2")
    assert os.environ["EVEN_G2_HOME_CHANNEL"] == "existing"
    assert calls == []


@pytest.mark.asyncio
async def test_sessions_new_creates_and_pushes_list(tmp_path, monkeypatch):
    a = _adapter(tmp_path)
    ws = FakeWS(); a._registry.register("g2", ws)

    created = _entry("new1", "", 0, 0)

    class NewStore(FakeStore):
        def get_or_create_session(self, source):
            return created
        def list_sessions(self, active_minutes=None):
            return [created, _entry("old", "Old", 0, 0)]

    a.set_session_store(NewStore())

    async def _noop(chat_id, command, **kwargs):
        pass
    monkeypatch.setattr(a, "_dispatch_command", _noop)

    await a.on_sessions_new("g2")

    assert a._session_by_chat["g2"] == "new1"
    assert ws.sent[0] == {"t": "active", "id": "new1"}
    frame = next(m for m in ws.sent if m["t"] == "sessions")
    assert frame["active"] == "new1"
    assert "new1" in [it["id"] for it in frame["items"]]
    assert next(it for it in frame["items"] if it["id"] == "new1")["title"] == "New session"
    assert ws.sent[-1] == {"t": "history", "id": "new1", "items": [], "ok": True}


@pytest.mark.asyncio
async def test_sessions_new_suppresses_internal_reset_message(tmp_path, monkeypatch):
    a = _adapter(tmp_path)
    ws = FakeWS(); a._registry.register("g2", ws)
    created = _entry("new1", "", 0, 0)

    class NewStore(FakeStore):
        def get_or_create_session(self, source):
            return created
        def list_sessions(self, active_minutes=None):
            return [created]

    async def _handle_message(event):
        await a.send("g2", "Session reset")

    a.set_session_store(NewStore())
    monkeypatch.setattr(a, "handle_message", _handle_message)

    await a.on_sessions_new("g2")

    assert not any(m["t"] == "assistant.delta" for m in ws.sent)
    assert any(m["t"] == "sessions" and m["active"] == "new1" for m in ws.sent)
    assert any(m["t"] == "history" and m["id"] == "new1" and m["items"] == [] for m in ws.sent)
