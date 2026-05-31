# hermes-evenhub-bridge

![Even Realities × Hermes Agent Bridge](docs/banner.png)

**Even Realities G2 smart glasses as a first-class [Hermes](https://github.com/NousResearch/hermes-agent) platform.**

This plugin registers `even_g2` as a Hermes gateway platform. It hosts a local WebSocket and
can configure a private Tailscale Serve `wss://` endpoint for the Even companion app; inbound
text and voice are dispatched through the Hermes gateway, and the agent's streamed reply,
tool-call status, session switching, and transcripts flow back to the glasses' 576×288 display.

> **This repo is the Hermes-side plugin only.** The glasses-side app (the TypeScript Even Hub
> WebView app that runs on the phone) is its sister repo,
> [`hermes-even-hub-app`](https://github.com/huntsyea/hermes-even-hub-app).
> The two halves talk only through the [JSON frame protocol](docs/protocol.md).

![Architecture](docs/diagrams/architecture.svg)

## What it does

- **Bridges the glasses to your agent** — text or voice on the glasses becomes a gateway turn;
  the reply streams back token-by-token to the tiny display.
- **Streams as deltas** — the adapter diffs the gateway's accumulated reply into append-only
  `assistant.delta` frames, and surfaces tool activity (`tool.start`/`tool.end`).
- **Transcribes voice on-device** — parakeet on the Apple Neural Engine, with a universal
  `whisper-tiny` fallback.
- **Self-installs** — `hermes plugins install` + one gateway restart pulls the Python deps automatically;
  on macOS, the signed ASR sidecar is fetched when you download a parakeet model.

## Install

```bash
hermes plugins install huntsyea/hermes-evenhub-bridge
```

Then:

1. **Enable and restart** — `hermes plugins enable hermes-evenhub-bridge && hermes gateway restart`.
   The first start auto-installs `websockets`/`numpy`/`faster-whisper` (a few minutes on a cold
   cache; falls back to a clear "install manually" message if it can't).
2. **Run setup** — open the **Even Realities G2** dashboard tab and click
   **Configure local bridge**, then **Enable Tailscale Serve**. The CLI equivalent is
   `hermes even-g2 setup`. Setup generates `EVENHUB_BRIDGE_TOKEN` when missing, binds the
   bridge to loopback, and creates a private Tailscale `wss://` app URL.
3. **Point the companion app at the bridge** — paste the dashboard/CLI **App URL** and pairing
   token into the Even companion app. The recommended URL looks like
   `wss://<machine>.<tailnet>.ts.net:8443`.
4. **Approve pairing** — the first turn returns a code: `hermes pairing approve even_g2 <code>`.

## Docs

- [Architecture](docs/architecture.md) — components, the streaming/turn-done internals, and the turn sequence diagrams
- [Tailscale Serve setup plan](docs/tailscale-serve-setup-plan.md) — implementation plan and non-goals for the private WSS setup
- [Wire protocol](docs/protocol.md) — the client/server frame contract
- [Configuration](docs/configuration.md) — env vars, Tailscale networking, ASR, dashboard, CLI
- [FAQ & troubleshooting](docs/faq.md)
- [Repository governance](docs/repository-governance.md) — required checks, review gates, and release-tag rules
- [Security](SECURITY.md) · [Support](SUPPORT.md) · [Contributing](CONTRIBUTING.md) ·
  [Code of Conduct](CODE_OF_CONDUCT.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)

## License

[MIT](LICENSE) © Hunter Yeagley
