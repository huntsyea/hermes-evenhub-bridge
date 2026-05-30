import asyncio, json, pytest, websockets
from hermes_evenhub_bridge.server import BridgeServer
from hermes_evenhub_bridge.config import BridgeConfig
from hermes_evenhub_bridge.connections import ConnectionRegistry


class FakeAdapter:
    def __init__(self, fail_text=False):
        self.calls = []
        self._fail_text = fail_text
    async def on_text(self, chat_id, text):
        if self._fail_text:
            raise RuntimeError("boom")
        self.calls.append(("text", chat_id, text))
    async def on_sessions_list(self, chat_id): self.calls.append(("list", chat_id))
    async def on_sessions_switch(self, chat_id, sid): self.calls.append(("switch", chat_id, sid))
    async def on_sessions_new(self, chat_id): self.calls.append(("new", chat_id))
    async def on_stop(self, chat_id): self.calls.append(("stop", chat_id))
    async def on_audio(self, chat_id, pcm): self.calls.append(("audio", chat_id, bytes(pcm)))
    def refresh_status(self): pass


async def _serve(token="secret", adapter=None):
    reg = ConnectionRegistry()
    ad = adapter or FakeAdapter()
    srv = BridgeServer(BridgeConfig(ws_host="127.0.0.1", ws_port=0, token=token), reg, ad)
    port = await srv.start()
    return srv, reg, ad, port


async def _hello(port, token="secret"):
    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
    await ws.send(json.dumps({"t": "hello", "token": token, "device": "g2"}))
    return ws


@pytest.mark.asyncio
async def test_bad_token_is_rejected():
    srv, reg, ad, port = await _serve()
    try:
        async with await websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"t": "hello", "token": "wrong", "device": "g2"}))
            with pytest.raises(websockets.ConnectionClosed):
                await asyncio.wait_for(ws.recv(), 2)
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_empty_configured_token_rejects_all():
    srv, reg, ad, port = await _serve(token="")
    try:
        async with await websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"t": "hello", "token": "", "device": "g2"}))
            with pytest.raises(websockets.ConnectionClosed):
                await asyncio.wait_for(ws.recv(), 2)
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_malformed_hello_closes():
    srv, reg, ad, port = await _serve()
    try:
        async with await websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send("not json")
            with pytest.raises(websockets.ConnectionClosed):
                await asyncio.wait_for(ws.recv(), 2)
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_hello_ok_then_text_and_audio_routed():
    srv, reg, ad, port = await _serve()
    try:
        async with await _hello(port) as ws:
            ok = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert ok["t"] == "hello.ok"
            assert reg.is_connected("g2")
            await ws.send(json.dumps({"t": "text", "text": "hi"}))
            await ws.send(json.dumps({"t": "audio.start"}))
            await ws.send(b"\x01\x02\x03\x04")
            await ws.send(json.dumps({"t": "audio.stop"}))
            await asyncio.sleep(0.2)
        assert ("text", "g2", "hi") in ad.calls
        assert ("audio", "g2", b"\x01\x02\x03\x04") in ad.calls
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_pcm_overflow_drops_stream(monkeypatch):
    import hermes_evenhub_bridge.server as srv_mod
    monkeypatch.setattr(srv_mod, "_MAX_PCM_BYTES", 4)  # tiny cap for the test
    srv, reg, ad, port = await _serve()
    try:
        async with await _hello(port) as ws:
            await asyncio.wait_for(ws.recv(), 2)  # hello.ok
            await ws.send(json.dumps({"t": "audio.start"}))
            await ws.send(b"\x01\x02\x03\x04\x05\x06")  # exceeds the 4-byte cap
            err = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert err["t"] == "error"
            await ws.send(json.dumps({"t": "audio.stop"}))
            await asyncio.sleep(0.2)
        # Overflowed stream is discarded: on_audio gets empty bytes, not the flood.
        audio = [c for c in ad.calls if c[0] == "audio"]
        assert audio == [("audio", "g2", b"")]
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_non_string_token_rejected():
    srv, reg, ad, port = await _serve()
    try:
        async with await websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"t": "hello", "token": 12345, "device": "g2"}))
            with pytest.raises(websockets.ConnectionClosed):
                await asyncio.wait_for(ws.recv(), 2)
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_binary_outside_audio_stream_ignored():
    srv, reg, ad, port = await _serve()
    try:
        async with await _hello(port) as ws:
            await asyncio.wait_for(ws.recv(), 2)  # hello.ok
            await ws.send(b"\xde\xad")            # no audio.start yet -> ignored
            await ws.send(json.dumps({"t": "audio.start"}))
            await ws.send(b"\x01\x02")
            await ws.send(json.dumps({"t": "audio.stop"}))
            await asyncio.sleep(0.2)
        audio = [c for c in ad.calls if c[0] == "audio"]
        assert audio == [("audio", "g2", b"\x01\x02")]
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_bad_field_sends_error_and_keeps_connection():
    srv, reg, ad, port = await _serve()
    try:
        async with await _hello(port) as ws:
            await asyncio.wait_for(ws.recv(), 2)  # hello.ok
            await ws.send(json.dumps({"t": "sessions.switch"}))  # missing id
            err = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert err["t"] == "error"
            await ws.send(json.dumps({"t": "text", "text": "still alive"}))
            await asyncio.sleep(0.2)
        assert ("text", "g2", "still alive") in ad.calls
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_adapter_exception_sends_error_and_keeps_connection():
    srv, reg, ad, port = await _serve(adapter=FakeAdapter(fail_text=True))
    try:
        async with await _hello(port) as ws:
            await asyncio.wait_for(ws.recv(), 2)  # hello.ok
            await ws.send(json.dumps({"t": "text", "text": "boom"}))
            err = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert err["t"] == "error"
            await ws.send(json.dumps({"t": "sessions.new"}))   # connection still alive
            await asyncio.sleep(0.2)
        assert ("new", "g2") in ad.calls
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_audio_buffer_cleared_after_failed_on_audio():
    class FailingOnceAudio(FakeAdapter):
        def __init__(self):
            super().__init__()
            self._failed = False
        async def on_audio(self, chat_id, pcm):
            if not self._failed:
                self._failed = True
                raise RuntimeError("boom")
            self.calls.append(("audio", chat_id, bytes(pcm)))

    srv, reg, ad, port = await _serve(adapter=FailingOnceAudio())
    try:
        async with await _hello(port) as ws:
            await asyncio.wait_for(ws.recv(), 2)  # hello.ok
            await ws.send(json.dumps({"t": "audio.start"}))
            await ws.send(b"\xaa\xbb")
            await ws.send(json.dumps({"t": "audio.stop"}))   # on_audio raises
            err = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert err["t"] == "error"
            await ws.send(json.dumps({"t": "audio.start"}))
            await ws.send(b"\x01")
            await ws.send(json.dumps({"t": "audio.stop"}))
            await asyncio.sleep(0.2)
        audio = [c for c in ad.calls if c[0] == "audio"]
        assert audio == [("audio", "g2", b"\x01")]   # no leftover bytes from the failed stream
    finally:
        await srv.stop()
