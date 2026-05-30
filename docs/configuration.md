# Configuration

All configuration is environment variables (in `~/.hermes/.env` or the gateway env).

| Variable | Default | Purpose |
|---|---|---|
| `EVENHUB_BRIDGE_TOKEN` | — (**required**) | Shared pairing secret; the hello handshake is rejected without it. Treat it like a root credential — see [SECURITY.md](../SECURITY.md). |
| `EVENHUB_BRIDGE_HOST` | `0.0.0.0` | WebSocket bind host. |
| `EVENHUB_BRIDGE_PORT` | `8765` | WebSocket bind port. |
| `EVENHUB_BRIDGE_NET` | `both` | Reachability mode: `both` \| `tailnet` \| `lan`. |
| `EVENHUB_MAX_PCM_BYTES` | `8388608` | Cap on buffered PCM per audio stream (anti-OOM). |
| `EVENHUB_ASR_MODEL` | — | Force the active ASR model (highest precedence). |
| `EVENHUB_ASR_SIDECAR_BIN` | `~/.hermes/even_g2/bin/g2-asr-sidecar` | Path to the parakeet sidecar binary. |
| `EVENHUB_ASR_SIDECAR_REPO` | `huntsyea/hermes-evenhub-bridge` | GitHub repo to fetch the prebuilt sidecar from (forks/mirrors). |
| `EVENHUB_ASR_SIDECAR_TEAM_ID` | `5J4FVDUC9M` | Apple Team ID the downloaded sidecar must be signed by (`""` disables the check). |
| `EVENHUB_ASR_STATE` | `~/.hermes/even_g2_asr.json` | Active-model state file (written by `asr set`). |

## Networking (Tailscale / LAN)

A raw LAN IP breaks the moment the phone leaves the Wi-Fi, so the bridge prefers
**Tailscale** when available and advertises a stable URL reachable anywhere on your tailnet.

- **URL precedence:** Tailscale MagicDNS name → Tailscale IP → LAN IP. A pinned
  `EVENHUB_BRIDGE_HOST` (a specific interface) overrides this so the advertised URL matches
  what the socket actually binds.
- **`EVENHUB_BRIDGE_NET`:** `both` (default — bind `0.0.0.0`, advertise the tailnet name) ·
  `tailnet` (bind the Tailscale interface only) · `lan` (bind `0.0.0.0`, advertise the LAN
  IP, skip Tailscale detection).
- Tailscale is detected via `tailscale status --json`; if it isn't running, the bridge falls
  back to the LAN IP. **It never installs or brings up Tailscale.**

The advertised URL is shown by `hermes even-g2 url`, the dashboard ("Glasses URL"),
and the status file.

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
active session), the **Glasses URL** to paste into the app, and the ASR model picker with a
one-click **Download** for the sidecar. Backend routes mount at
`/api/plugins/hermes-evenhub-bridge/`.

## CLI

```bash
hermes even-g2 url                 # print the ws:// URL the glasses should use
hermes even-g2 asr list            # list models + which are installed/active
hermes even-g2 asr download <name> # fetch a model (auto-downloads the sidecar on macOS)
hermes even-g2 asr set <name>      # set the active model (takes effect next voice command)
```
