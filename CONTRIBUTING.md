# Contributing

Thanks for your interest! This is the **Hermes-side plugin** for Even Realities G2.
The glasses-side app is its sister repo,
[hermes-even-hub-app](https://github.com/huntsyea/hermes-even-hub-app).

## Layout

This is a **directory plugin** (the official Hermes model): the package files live at
the repo **root** so `hermes plugins install huntsyea/hermes-evenhub-bridge` works. The
`pyproject.toml` is for dev tooling only — it does not build/install the package.

## Dev setup

```bash
uv sync
uv run pytest -m "not gateway"   # gateway-free suite (deterministic)
uv run ruff check .
```

The full suite has tests that need the Hermes gateway (marked `@pytest.mark.gateway`).
Run them with the gateway available:

```bash
# either: a local Hermes checkout (auto-detected at ~/.hermes/hermes-agent)
uv run pytest -m gateway
# or: pull it from PyPI
uv run --with hermes-agent pytest -m gateway
```

## Pull requests

- CI must pass (`ruff` + the gateway-free suite, Python 3.11–3.13).
- The **wire protocol is a contract** — if you change `protocol.py`, mirror it in the
  glasses-app `protocol.ts` and note it in the PR.
- Review the [security model](SECURITY.md) for anything touching the WebSocket auth,
  audio handling, subprocess execution, or the sidecar download.

## Security

Report vulnerabilities **privately** via GitHub Security Advisories — see `SECURITY.md`.
