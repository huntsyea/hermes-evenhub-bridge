"""Fake sidecar for FluidAudioBackend tests. Speaks the framed protocol on stdio.

Modes (via --mode): ok | error | crash | hang | missing.
"""
import json
import struct
import sys
import time

HEADER = struct.Struct(">I")


def write_frame(payload: bytes) -> None:
    sys.stdout.buffer.write(HEADER.pack(len(payload)) + payload)
    sys.stdout.buffer.flush()


def read_frame() -> bytes:
    head = sys.stdin.buffer.read(4)
    if len(head) < 4:
        raise EOFError
    (n,) = HEADER.unpack(head)
    return sys.stdin.buffer.read(n)


def main() -> None:
    mode = "ok"
    model = "v2"
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--mode" and i + 1 < len(args):
            mode = args[i + 1]
        if a == "--model-version" and i + 1 < len(args):
            model = args[i + 1]

    if "--download" in args:
        sys.exit(0)
    if "--check" in args:
        sys.exit(0 if mode != "missing" else 1)

    if mode == "nostart":
        sys.exit(1)

    write_frame(json.dumps({"ready": True, "model": f"parakeet-tdt-0.6b-{model}"}).encode())
    first = True
    while True:
        try:
            pcm = read_frame()
        except EOFError:
            return
        if mode == "hang":
            time.sleep(30)
        if mode == "error":
            write_frame(json.dumps({"error": "boom"}).encode())
            continue
        if mode == "crash" and not first:
            sys.exit(1)
        first = False
        write_frame(json.dumps({"text": f"stub:{len(pcm)}"}).encode())


if __name__ == "__main__":
    main()
