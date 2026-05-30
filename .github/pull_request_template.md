## What & why

<!-- What does this change and why? Link any issue. -->

## Checklist
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest -m "not gateway"` passes (gateway-free suite)
- [ ] If the wire protocol changed, `protocol.py` and the glasses-app `protocol.ts` were updated together
- [ ] Docs/README updated if behavior or config changed
- [ ] Considered security impact (see SECURITY.md threat model)
