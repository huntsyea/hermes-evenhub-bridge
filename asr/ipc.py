"""Length-prefixed binary framing shared with the Swift sidecar.

Frame = [4-byte big-endian length][payload]. Mirror this in main.swift.
"""
from __future__ import annotations

import struct

_HEADER = struct.Struct(">I")


def encode_frame(payload: bytes) -> bytes:
    return _HEADER.pack(len(payload)) + payload


def _read_exactly(stream, n: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < n:
        chunk = stream.read(n - len(chunks))
        if not chunk:
            raise EOFError("stream closed before frame complete")
        chunks.extend(chunk)
    return bytes(chunks)


def read_frame(stream) -> bytes:
    (length,) = _HEADER.unpack(_read_exactly(stream, 4))
    return _read_exactly(stream, length)
