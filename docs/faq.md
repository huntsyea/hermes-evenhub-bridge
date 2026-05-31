# FAQ & Troubleshooting

## FAQ

**Do I need the sidecar / a Swift toolchain?**
No. `whisper-tiny` works everywhere out of the box. The parakeet sidecar is an optional
macOS speed-up that auto-downloads — you never build it unless you're hacking on it.

**Does it work when my phone is on cellular / a different network?**
Yes, if both the Mac and the phone are on the same Tailscale tailnet — that's what the
Tailscale URL is for. On the same LAN, the LAN IP works too.

**Why does the first `hermes gateway restart` after install take a while?**
It's the one-time dependency install. Subsequent starts are instant (a fast import probe).
If it fails it won't re-hang every restart — it records a cooldown and tells you how to
install manually.

**Does the plugin install or configure Tailscale for me?**
It configures **Tailscale Serve** after you explicitly click **Enable Tailscale Serve** or run
`hermes even-g2 setup`. It does not install Tailscale, log you in, run `tailscale up`, or
enable Funnel.

**Is the glasses app in this repo?**
No — this repo is the Hermes-side plugin. The glasses app is in the
[`hermes-even-hub-app`](https://github.com/huntsyea/hermes-even-hub-app) repo.

**How do I update after a new release?**
```bash
hermes plugins update hermes-evenhub-bridge && hermes gateway restart
```
If the update changes dashboard API routes, restart the Hermes dashboard process too; those
routes are mounted only when the dashboard starts.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Platform shows **unavailable** | `EVENHUB_BRIDGE_TOKEN` isn't set, or dependency auto-install failed (check the gateway log for "dependencies still missing" and install `requirements.txt` manually). |
| Companion app can't connect | Wrong URL or token. Re-run `hermes even-g2 setup` or check the dashboard **App URL**; if you regenerate the token, paste the new value into the app and restart Hermes Gateway. |
| Setup says Tailscale is offline | Install Tailscale, log in with `tailscale up`, and make sure MagicDNS is enabled for the tailnet. |
| First turn returns a code, not a reply | Pairing gate — run `hermes pairing approve even_g2 <code>`. |
| Voice always uses whisper, never parakeet | Not on macOS/arm64, or the sidecar download/verification failed (check the gateway log). |
| "Connected Platforms" pill shows `even_g2`, not the label | A stock Hermes frontend limitation (it renders the raw platform key). Not a bug here. |
