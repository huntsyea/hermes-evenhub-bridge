# Tailscale Serve Setup Plan

## Goal

Make the Hermes bridge do the repetitive setup work for the open-source connection style:
a local bridge on loopback, private Tailscale Serve WSS in front of it, and a runtime URL/token
that the Even companion app can enter without rebuilding.

## Architecture

1. Keep the existing bridge protocol unchanged. The app still opens a WebSocket and sends the
   existing `hello` frame with `EVENHUB_BRIDGE_TOKEN`.
2. Bind the bridge to `127.0.0.1:<EVENHUB_BRIDGE_PORT>` for the recommended path.
3. Configure Tailscale Serve with:

   ```bash
   tailscale serve --https=<EVENHUB_BRIDGE_SERVE_PORT> --bg http://127.0.0.1:<EVENHUB_BRIDGE_PORT>
   ```

4. Persist the resulting `wss://<machine>.<tailnet>.ts.net:<port>` URL as
   `EVENHUB_BRIDGE_PUBLIC_URL`.
5. Surface the same setup flow through the dashboard and `hermes even-g2 setup`.

## Implementation Steps

1. Add setup helpers that can generate a token, persist loopback bridge env values, detect
   Tailscale status, run `tailscale serve`, and persist the public WSS URL.
2. Add dashboard API routes for setup status, local bridge configuration, and Tailscale Serve
   activation.
3. Update the dashboard connection panel with explicit setup buttons, token status, App URL,
   Local bridge URL, Tailscale status, and restart guidance.
4. Update the CLI so `hermes even-g2 setup` performs the same flow and `hermes even-g2 url`
   prefers the configured WSS URL.
5. Update documentation and security notes to define this as the prescribed setup.
6. Cover the flow with unit tests for config parsing, Tailscale detection, setup persistence,
   subprocess hardening, dashboard API behavior, CLI dispatch, and status defaults.

## Non-goals

- Do not add a hosted relay.
- Do not enable Tailscale Funnel.
- Do not install Tailscale or run `tailscale up` for the user.
- Do not change frame names, payloads, token handshake semantics, or pairing behavior.
