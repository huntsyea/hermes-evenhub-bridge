# AGENTS.md

## Project Overview

- This repository is the Hermes-side directory plugin for Even Realities G2 smart glasses.
- The repo root is the plugin package boundary: `plugin.yaml`, `__init__.py`, and the Python modules must stay at the root so `hermes plugins install huntsyea/hermes-evenhub-bridge` works.
- `server.py` owns the WebSocket transport and authentication handshake; `adapter.py` integrates with the Hermes gateway; `connections.py` owns active socket/session state; `asr/` owns transcription backends and fallback behavior.
- `dashboard/` is a hand-written Hermes dashboard extension. `dashboard/dist/index.js` is committed directly; there is no dashboard build step in this repo.
- `sidecar/` contains the macOS Apple Silicon Swift ASR sidecar. It is built and released separately from the Python plugin.
- The glasses-side app is a sister repository. The shared JSON frame protocol is the contract between this repo's `protocol.py` and the glasses app's `protocol.ts`.

## Setup Commands

- Install dependencies: `uv sync --locked`
- Verify the lockfile: `uv lock --check`
- Runtime dependencies are mirrored in `requirements.txt` because the plugin self-installs them into the Hermes gateway interpreter on first load.
- Do not treat `pyproject.toml` as an installable package build target; `[tool.uv].package = false` is intentional.

## Development Workflow

- Run the deterministic local loop before changing behavior:
  - `uv lock --check`
  - `uv run --locked ruff check .`
  - `uv run --locked pytest -m "not gateway"`
- Run gateway-marked tests only when Hermes gateway support is available:
  - Local checkout path: `uv run pytest -m gateway`
  - PyPI gateway dependency: `uv run --with hermes-agent pytest -m gateway`
- Build the Swift sidecar from its package directory: `cd sidecar && swift build -c release`
- Regenerate diagrams after editing `docs/diagrams/*.mmd`: `scripts/render-diagrams.sh`

## Testing Instructions

- Primary test suite: `uv run --locked pytest -m "not gateway"`.
- Targeted tests: `uv run --locked pytest tests/test_<area>.py`.
- Gateway tests are marked with `@pytest.mark.gateway` and are intentionally separate from the deterministic suite.
- CI runs `ruff` and the gateway-free test suite on Python 3.11, 3.12, and 3.13. It also runs gateway integration as a best-effort canary.
- CodeQL analyzes Python and GitHub Actions workflows.

## Code Style

- Keep changes simple and local to the module responsibility documented in `docs/architecture.md`.
- Prefer small functions with explicit data flow over speculative abstractions. Add abstractions only when they remove real duplication or clarify a cross-module contract.
- Follow existing Python style: type hints where useful, `asyncio` patterns consistent with surrounding code, and no broad formatting churn.
- Ruff is configured with line length 100 and lint selections `E9`, `F`, `B`, and `C4`.
- Preserve committed dashboard JavaScript as hand-written source unless a real build pipeline is introduced intentionally.
- For comments, match the existing English technical style and comment only non-obvious behavior.

## Protocol And Compatibility

- Treat `docs/protocol.md` as the wire-contract source for reviewers and agents.
- If `protocol.py` changes, update the glasses app's `protocol.ts` in the sister repository and call this out in the PR.
- Do not change frame names, payload shapes, authentication behavior, or turn-completion semantics without updating tests and documentation.
- Preserve `assistant.delta` append-only behavior and `turn.done` semantics unless the protocol documentation changes with the implementation.

## Security Considerations

- Read `SECURITY.md` before editing WebSocket auth, pairing, audio buffering, subprocess execution, sidecar download/install logic, dashboard API routes, or environment-variable handling.
- Treat `EVENHUB_BRIDGE_TOKEN` as the trust boundary. Do not log it, echo it in errors, or add test fixtures that normalize leaking it.
- Keep PCM/audio buffering bounded and preserve constant-time token comparison.
- Official sidecar releases must remain Developer ID signed, notarized, checksum-verified, and tied to protected `sidecar-v*` tags.

## Build And Release

- Keep version declarations synchronized across `__init__.py`, `pyproject.toml`, `plugin.yaml`, and `dashboard/manifest.json`.
- Release plugin versions from `main` only.
- Sidecar release tags use `sidecar-v<version>` and must point at the same commit as the plugin version they serve.
- Do not replace published sidecar assets. Publish a new patch version instead.
- Release governance expectations are documented in `docs/repository-governance.md`.

## PR Review Instructions

- Start with correctness and contract risk: protocol compatibility, Hermes gateway behavior, WebSocket lifecycle, ASR fallback, dashboard API behavior, and security boundaries.
- Apply a KISS check before approving: reject unnecessary abstractions, speculative extension points, broad rewrites, and changes that make the small directory-plugin layout harder to reason about.
- Check relevant documentation for every behavior change:
  - `README.md` for user-facing behavior and install flow.
  - `docs/architecture.md` for module responsibilities and turn-flow details.
  - `docs/protocol.md` for frame contract changes.
  - `docs/configuration.md` for environment variable or CLI changes.
  - `SECURITY.md` for auth, network, audio, subprocess, sidecar, or dashboard-risk changes.
  - `CONTRIBUTING.md` and `docs/repository-governance.md` for required checks and release gates.
- Require tests for changed behavior. Prefer focused tests near the changed module, then run the gateway-free suite.
- For protocol changes, require evidence that the glasses-side `protocol.ts` was updated or a clear explanation of why it is unaffected.
- For version or release changes, verify all version files and sidecar tag rules stay in sync.
- Do not approve changes that leak secrets, weaken pairing/authentication, remove resource bounds, or make the auto-download path less verifiable.

## Pull Request Guidelines

- Required pre-review checks:
  - `uv lock --check`
  - `uv run --locked ruff check .`
  - `uv run --locked pytest -m "not gateway"`
- PRs that touch gateway integration should mention whether gateway-marked tests were run and how.
- PRs that touch the sidecar should mention the Swift build result and any signing/notarization impact.
- PRs that touch docs diagrams should include regenerated SVGs.
- Explicit user prompts override this file. If a nested `AGENTS.md` is added later, the nearest file governs that subtree.
