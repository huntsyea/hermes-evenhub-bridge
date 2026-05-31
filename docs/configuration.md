# Configuration

All configuration is environment variables (in `~/.hermes/.env` or the gateway env).

| Variable | Default | Purpose |
|---|---|---|
| `EVENHUB_BRIDGE_TOKEN` | — (**required**) | Shared pairing secret; the hello handshake is rejected without it. Treat it like a root credential — see [SECURITY.md](../SECURITY.md). |
| `EVENHUB_BRIDGE_HOST` | `0.0.0.0` | WebSocket bind host. |
| `EVENHUB_BRIDGE_PORT` | `8765` | WebSocket bind port. |
| `EVENHUB_BRIDGE_NET` | `both` | Reachability mode: `both` \| `tailnet` \| `lan`. |
| `EVENHUB_BRIDGE_PUBLIC_URL` | — | Preferred companion-app URL, normally written by setup after Tailscale Serve succeeds. |
| `EVENHUB_BRIDGE_SERVE_PORT` | `8443` | HTTPS/WSS port used by `tailscale serve`. |
| `EVENHUB_MAX_PCM_BYTES` | `8388608` | Cap on buffered PCM per audio stream (anti-OOM). |
| `EVENHUB_ASR_MODEL` | — | Force the active ASR model (highest precedence). |
| `EVENHUB_ASR_SIDECAR_BIN` | `~/.hermes/even_g2/bin/g2-asr-sidecar` | Path to the parakeet sidecar binary. |
| `EVENHUB_ASR_SIDECAR_REPO` | `huntsyea/hermes-evenhub-bridge` | GitHub repo to fetch the prebuilt sidecar from (forks/mirrors). |
| `EVENHUB_ASR_SIDECAR_TEAM_ID` | `5J4FVDUC9M` | Apple Team ID the downloaded sidecar must be signed by (`""` disables the check). |
| `EVENHUB_ASR_STATE` | `~/.hermes/even_g2_asr.json` | Active-model state file (written by `asr set`). |

## Recommended setup

The prescribed open-source setup is:

1. The bridge listens locally on `ws://127.0.0.1:8765`.
2. Tailscale Serve terminates TLS and forwards private tailnet traffic to that local socket:
   `tailscale serve --https=8443 --bg http://127.0.0.1:8765`.
3. The Even companion app connects to `wss://<machine>.<tailnet>.ts.net:8443` and sends the
   shared token in the `hello` frame.

The dashboard can perform steps 1-2 through the **Connection** panel:

- **Generate token** writes `EVENHUB_BRIDGE_TOKEN` when it is missing,
  `EVENHUB_BRIDGE_HOST=127.0.0.1`, `EVENHUB_BRIDGE_NET=lan`, and the current bridge port.
- **Regenerate token** replaces the existing `EVENHUB_BRIDGE_TOKEN` and shows the new token
  once. The old companion-app token stops working after the Hermes Gateway restart.
- **Enable Tailscale Serve** runs `tailscale serve` with argument-list subprocess execution
  and no Funnel exposure, then persists `EVENHUB_BRIDGE_PUBLIC_URL`.

Changing host, port, or token requires a Hermes Gateway restart because the adapter reads
bridge config at startup.

## Networking details

`hermes even-g2 url` prints `EVENHUB_BRIDGE_PUBLIC_URL` when configured. Without setup it
falls back to the legacy local `ws://` discovery path:

- **URL precedence:** configured public URL → Tailscale MagicDNS name → Tailscale IP → LAN IP.
- **`EVENHUB_BRIDGE_NET`:** `both` (default — bind `0.0.0.0`, advertise the tailnet name) ·
  `tailnet` (bind the Tailscale interface only) · `lan` (bind the configured host and skip
  Tailscale detection).
- Tailscale is detected via `tailscale status --json`. Setup can configure Tailscale Serve,
  but it does not install Tailscale or run `tailscale up`; the user owns Tailscale login.

## Voice / ASR

Transcription is pluggable and **degrades gracefully** — a voice command always produces a
transcript.

| Model | Backend | Platform | Notes |
|---|---|---|---|
| `parakeet-tdt-0.6b-v2` | Swift FluidAudio sidecar | macOS (Apple Silicon) | **Default.** Fast, Apple Neural Engine. |
| `parakeet-tdt-0.6b-v3` | Swift FluidAudio sidecar | macOS (Apple Silicon) | Multilingual. |
| `whisper-tiny` | faster-whisper (CPU) | any | **Universal fallback.** Weights self-download on first use. |

- **Active model resolution:** `EVENHUB_ASR_MODEL` env > state file (`asr set`) > default.
- **Sidecar auto-download:** on macOS/arm64, the first parakeet download fetches the prebuilt
  binary from this repo's Releases (checksum- *and* Developer-ID-signature-verified, streamed
  to disk). Elsewhere, or on failure, transcription stays on `whisper-tiny`.
- The sidecar binary is **Developer ID signed + notarized** (hardened runtime), so it runs
  without Gatekeeper prompts.

## Dashboard

The **Even Realities G2** tab at `/even-g2` shows live status (connected devices, mic state,
active session), the **App URL** to paste into the companion app, local bridge setup controls,
Tailscale Serve setup, and the ASR model picker with a one-click **Download** for the sidecar.
Backend routes mount at `/api/plugins/hermes-evenhub-bridge/`.

After updating this plugin, restart the Hermes dashboard process as well as the gateway when
dashboard API routes changed. The dashboard imports plugin API routes at process startup.

## CLI

```bash
hermes even-g2 setup               # configure token, loopback bridge, and Tailscale Serve
hermes even-g2 setup --skip-serve  # write local bridge env only
hermes even-g2 url                 # print the companion-app URL, preferring configured WSS
hermes even-g2 asr list            # list models + which are installed/active
hermes even-g2 asr download <name> # fetch a model (auto-downloads the sidecar on macOS)
hermes even-g2 asr set <name>      # set the active model (takes effect next voice command)
```
