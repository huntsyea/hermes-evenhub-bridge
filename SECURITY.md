# Security Policy

## Reporting a vulnerability

Please report security issues **privately** via GitHub Security Advisories
(repo → **Security → Report a vulnerability**) rather than a public issue. We aim to
acknowledge within a few days and coordinate disclosure once a fix is available.

## Threat model — read this before deploying

This plugin hosts a WebSocket that, once a client presents the shared
`EVENHUB_BRIDGE_TOKEN` **and** is approved through Hermes pairing, can send messages
that the Hermes agent executes **with full tool permissions**. In other words:

> **The token is the trust boundary. Anyone who holds `EVENHUB_BRIDGE_TOKEN` (and is
> paired) can drive your agent — including any tools it can run.**

Deploy accordingly:

- **Treat the token like a root credential.** Use a long random secret; never commit or
  log it. Rotate it if exposed.
- **Prefer the private WSS setup.** The dashboard/`hermes even-g2 setup` path binds the
  bridge to `127.0.0.1` and uses Tailscale Serve to expose
  `wss://<machine>.<tailnet>.ts.net:8443` only inside your tailnet. Do not enable Tailscale
  Funnel for this bridge.
- **Avoid raw LAN exposure.** The fallback transport is `ws://` (no TLS), so on a plain LAN
  the token and traffic are in cleartext. Don't expose port `8765` to untrusted networks or
  the public internet.
- **Pairing is per device.** A new device id triggers a fresh pairing code
  (`hermes pairing approve even_g2 <code>`); approve only devices you control.

## Hardening in place

- **Constant-time token comparison** (`hmac.compare_digest`) — the secret isn't probeable
  via response timing.
- **Bounded PCM buffering** — an authenticated client can't exhaust memory by flooding
  audio frames; the per-stream buffer is capped (`EVENHUB_MAX_PCM_BYTES`, default ~8 MiB).
- **Signed-binary verification** — the auto-downloaded ASR sidecar is checksum-verified
  **and** its Apple Developer ID signature / Team ID is verified before it's run, so a
  compromised release host can't substitute an unsigned or foreign-signed binary
  (`EVENHUB_ASR_SIDECAR_TEAM_ID` to override for forks).
- **Explicit setup actions** — the plugin does not mutate Tailscale on import or gateway
  startup. Tailscale Serve is configured only from the dashboard button or
  `hermes even-g2 setup`, and subprocess execution uses an argument list rather than a shell.

## Trust assumptions

- The Hermes gateway is trusted; this plugin runs in-process and inherits its privileges.
- The Hermes dashboard's auth gates the plugin's HTTP API (`/api/plugins/...`), including
  the privileged `POST /asr/download` (which fetches + runs the sidecar) and setup routes
  that write bridge env values or run `tailscale serve`. Keep the Hermes dashboard
  access-controlled.
- Local write access to `~/.hermes/plugins/hermes-evenhub-bridge/` is equivalent to code
  execution in the gateway (the plugin pip-installs its own `requirements.txt` on first
  load) — the same trust level as any installed plugin.
