import pytest
from hermes_evenhub_bridge.connections import ConnectionRegistry, StreamState


class FakeWS:
    def __init__(self): self.sent = []
    async def send(self, data): self.sent.append(data)


@pytest.mark.asyncio
async def test_register_send_and_unregister():
    reg = ConnectionRegistry()
    ws = FakeWS()
    reg.register("g2", ws)
    assert reg.is_connected("g2")
    assert reg.count() == 1
    await reg.send_frame("g2", '{"t":"x"}')
    assert ws.sent == ['{"t":"x"}']
    reg.unregister("g2")
    assert not reg.is_connected("g2")
    # send to missing chat is a no-op, not an error
    await reg.send_frame("g2", "{}")


def test_stream_state_delta_tracking():
    reg = ConnectionRegistry()
    reg.register("g2", FakeWS())
    st = reg.stream_state("g2")
    assert st.delta_for("hello") == "hello"      # first chunk: whole thing
    assert st.sent_len == 5
    assert st.delta_for("hello world") == " world"  # accumulated -> suffix
    st.reset()
    assert st.sent_len == 0
    assert st.delta_for("new") == "new"


def test_stream_state_strips_streaming_cursor():
    # The gateway appends the cursor " ▉" to in-progress frames and removes
    # it on the finalize edit. The cursor must NOT leak into glasses deltas,
    # and stripping the exact cursor must preserve legitimate trailing spaces.
    st = StreamState()
    assert st.delta_for("Hello  ▉") == "Hello "    # "Hello " + cursor " ▉"
    assert st.delta_for("Hello wor ▉") == "wor"
    assert st.delta_for("Hello world. ▉") == "ld."
    assert st.delta_for("Hello world.") == ""           # finalize: cursor gone


def test_unregister_is_ws_guarded():
    reg = ConnectionRegistry()
    old, new = FakeWS(), FakeWS()
    reg.register("g2", old)
    reg.register("g2", new)          # reconnect overwrites the socket
    reg.unregister("g2", old)        # stale teardown must NOT drop the new one
    assert reg.is_connected("g2")
    reg.unregister("g2", new)
    assert not reg.is_connected("g2")
