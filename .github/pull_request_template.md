## What & why

<!-- What does this change and why? Link any issue. -->

## Checklist
- [ ] `uv lock --check` passes
- [ ] `uv run --locked ruff check .` passes
- [ ] `uv run --locked pytest -m "not gateway"` passes (gateway-free suite)
- [ ] If the wire protocol changed, `protocol.py` and the glasses-app `protocol.ts` were updated together
- [ ] Docs/README updated if behavior or config changed
- [ ] Considered security impact (see SECURITY.md threat model)
- [ ] Release/version changes keep `__init__.py`, `pyproject.toml`, `plugin.yaml`, `dashboard/manifest.json`, and sidecar tags in sync
