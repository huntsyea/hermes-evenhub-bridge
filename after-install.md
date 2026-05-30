# hermes-evenhub-bridge — installed ✓

Even Realities G2 smart glasses as a Hermes **platform** adapter. The plugin hosts a
WebSocket the glasses connect to; inbound messages flow through the gateway and the
agent's streamed replies flow back.

## 1. Set the pairing secret

In `~/.hermes/.env`:

```
EVENHUB_BRIDGE_TOKEN=<shared-secret>
```

The platform reports **unavailable** until this is set. Optional:
`EVENHUB_BRIDGE_HOST` (default `0.0.0.0`), `EVENHUB_BRIDGE_PORT` (default `8765`),
`EVENHUB_BRIDGE_NET` (`both` | `tailnet` | `lan`, default `both`).

## 2. Enable and restart

```bash
hermes plugins enable hermes-evenhub-bridge
hermes gateway restart
```

On first start the plugin **auto-installs its Python dependencies**
(`websockets`, `numpy`, `faster-whisper`) into the Hermes environment — no manual
pip step. If that ever fails (offline / locked-down env), install them yourself and
restart:

```bash
<your-hermes-python> -m pip install -r ~/.hermes/plugins/hermes-evenhub-bridge/requirements.txt
```

## 3. Point the glasses at the bridge

Get the ready-to-use URL (prefers your Tailscale MagicDNS name, which works from
anywhere on the tailnet; otherwise the LAN IP):

```bash
hermes-evenhub-bridge url
```

It's also shown on the **Even Realities G2** dashboard tab (`/even-g2`) as **Glasses
URL**. Put that URL in the glasses app's `.env.local` as `VITE_BRIDGE_LAN_URL`, and add
it to `app.json`'s `network` whitelist (exact match).

A newly connected device is **pairing-gated** — its first turn returns a pairing code:

```bash
hermes pairing approve even_g2 <code>
```

## Voice / ASR

Works out of the box with **`whisper-tiny`** (CPU; weights self-download on first use).
For the faster default (`parakeet-tdt-0.6b-v2`, Apple Neural Engine) on **macOS (Apple
Silicon)**, click **Download** on the dashboard's transcription panel — it auto-fetches
the prebuilt sidecar binary and model weights. Or from the CLI:

```bash
hermes-evenhub-bridge asr download parakeet-tdt-0.6b-v2
hermes-evenhub-bridge asr set parakeet-tdt-0.6b-v2
```

> The sidecar is unsigned; if macOS Gatekeeper blocks it, approve it once in
> System Settings → Privacy & Security. Non-macOS hosts stay on whisper automatically.

Source & full docs: https://github.com/huntsyea/even-g2-hermes
