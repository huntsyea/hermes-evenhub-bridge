# g2-asr-sidecar

Swift executable wrapping [FluidAudio](https://github.com/FluidInference/FluidAudio) (Parakeet TDT 0.6B) as the ASR engine for the Even G2 bridge. Communicates with the Python `FluidAudioBackend` over framed stdio.

**Requires:** macOS 14+, Apple Silicon (CoreML).

---

## Building

```bash
cd sidecar
swift build -c release
```

Binary lands at: `sidecar/.build/release/g2-asr-sidecar`

Set `EVENHUB_ASR_SIDECAR_BIN` in the bridge environment to override the default binary path used by `FluidAudioBackend`:

```bash
export EVENHUB_ASR_SIDECAR_BIN=/path/to/g2-asr-sidecar
```

---

## CLI flags

| Flag | Description |
|------|-------------|
| `--model-version v2\|v3` | Select Parakeet model variant (default: `v2`) |
| `--download` | Download the model then exit 0 (exit 1 on failure) |
| `--check` | Download/load model to verify it works, then exit 0 (exit 1 on failure) |

---

## Wire protocol

Mirrors `asr/ipc.py`. Every message in both directions is a **length-prefixed frame**:

```
[ 4-byte big-endian uint32 length ][ payload bytes ]
```

### Startup handshake

After launch, the sidecar writes one frame to stdout:

```json
{"ready": true, "model": "parakeet-tdt-0.6b-v2"}
```

The Python side blocks until this frame arrives before marking the backend ready.

### Per-request

Python writes one frame containing **raw PCM audio**: signed 16-bit little-endian, 16 kHz, mono.

Sidecar replies with one frame — either success:

```json
{"text": "transcribed words here"}
```

or error:

```json
{"error": "description of what went wrong"}
```

### EOF / shutdown

When stdin reaches EOF the sidecar exits cleanly.

---

## Platform

macOS / Apple Silicon only. CoreML acceleration is required; the FluidAudio library does not support x86_64 or non-Apple platforms.
