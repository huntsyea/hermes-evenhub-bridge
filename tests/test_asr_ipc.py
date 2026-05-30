import io
import pytest
from hermes_evenhub_bridge.asr.ipc import encode_frame, read_frame


def test_encode_prepends_4byte_be_length():
    assert encode_frame(b"abc") == b"\x00\x00\x00\x03abc"


def test_round_trip():
    buf = io.BytesIO(encode_frame(b"hello world"))
    assert read_frame(buf) == b"hello world"


def test_read_frame_raises_on_truncated_stream():
    buf = io.BytesIO(b"\x00\x00\x00\x05ab")  # claims 5 bytes, only 2 present
    with pytest.raises(EOFError):
        read_frame(buf)
