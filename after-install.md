# hermes-evenhub-bridge — installed ✓

Even Realities G2 smart glasses as a Hermes **platform** adapter. The plugin hosts a
LAN WebSocket the glasses connect to; inbound messages flow through the gateway and the
agent's streamed replies flow back.

## 1. Install Python dependencies

This plugin needs `faster-whisper`, `numpy`, and `websockets` in the **same** Python
environment that runs Hermes. Install them there:

```bash
# Adjust the path if your Hermes venv lives elsewhere
~/.hermes/hermes-agent/venv/bin/pip install -r ~/.hermes/plugins/hermes-evenhub-bridge/requirements.txt
```

## 2. Set the pairing secret

In `~/.hermes/.env`:

```
EVENHUB_BRIDGE_TOKEN=<shared-secret>
```

The platform reports **unavailable** until this is set. Optional:
`EVENHUB_BRIDGE_HOST` (default `0.0.0.0`), `EVENHUB_BRIDGE_PORT` (default `8765`).

## 3. Enable and restart

```bash
hermes plugins enable hermes-evenhub-bridge
hermes gateway restart
```

## 4. Connect the glasses

Point the glasses app at `ws://<host>:8765` with the same token. G2 appears under
**Connected Platforms**, with an **Even Realities G2** dashboard tab at `/even-g2`.
A newly connected device is **pairing-gated** — its first turn returns a pairing code:

```bash
hermes pairing approve even_g2 <code>
```

## Voice / ASR

Out of the box, transcription uses **`whisper-tiny`** (faster-whisper, CPU) — no extra
setup. For the faster default (`parakeet-tdt-0.6b-v2`, Apple Neural Engine) you need the
Swift sidecar, which is **not** shipped in this install. Build it from the source repo
(`bridge/sidecar/`) and point `EVENHUB_ASR_SIDECAR_BIN` at the binary, then:

```bash
hermes-evenhub-bridge asr download parakeet-tdt-0.6b-v2
hermes-evenhub-bridge asr set parakeet-tdt-0.6b-v2
```

Source & full docs: https://github.com/huntsyea/even-g2-hermes
