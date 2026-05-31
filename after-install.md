# hermes-evenhub-bridge — installed ✓

Even Realities G2 smart glasses as a Hermes **platform** adapter. The plugin hosts a
WebSocket the glasses connect to; inbound messages flow through the gateway and the
agent's streamed replies flow back.

## 1. Enable and restart

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

## 2. Configure private WSS access

Open the **Even Realities G2** dashboard tab and use the **Connection** panel:

1. Click **Configure local bridge**. This writes a long `EVENHUB_BRIDGE_TOKEN` if one is
   missing and switches the bridge to loopback settings.
2. Restart Hermes Gateway if the dashboard says a restart is required.
3. Click **Enable Tailscale Serve**. This runs:

```bash
tailscale serve --https=8443 --bg http://127.0.0.1:8765
```

The CLI equivalent is:

```bash
hermes even-g2 setup
```

Setup requires Tailscale to already be installed, logged in, and MagicDNS-enabled. The plugin
does not install Tailscale or enable Funnel.

## 3. Point the companion app at the bridge

Paste the dashboard **App URL** and token into the Even companion app. The URL should look
like `wss://<machine>.<tailnet>.ts.net:8443`.

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
hermes even-g2 asr download parakeet-tdt-0.6b-v2
hermes even-g2 asr set parakeet-tdt-0.6b-v2
```

> The sidecar is Developer ID signed + notarized, so it runs without Gatekeeper prompts.
> Non-macOS hosts stay on whisper automatically.

Source & full docs: https://github.com/huntsyea/hermes-evenhub-bridge
