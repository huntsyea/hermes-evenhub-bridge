"""Hermes plugin entry point for the Even Realities G2 platform adapter."""
from __future__ import annotations

import os


def register(ctx) -> None:
    from .adapter import EvenG2Adapter
    from . import hooks

    def _factory(cfg):
        adapter = EvenG2Adapter(cfg)
        hooks.bind(adapter)
        return adapter

    ctx.register_platform(
        name="even_g2",
        label="Even Realities G2",
        adapter_factory=_factory,
        check_fn=lambda: bool(os.environ.get("EVENHUB_BRIDGE_TOKEN")),
        emoji="👓",
        platform_hint=("You are talking to the user through Even Realities G2 "
                       "smart glasses with a tiny display; keep replies short."),
    )
    ctx.register_hook("pre_tool_call", hooks.pre_tool_call)
    ctx.register_hook("post_tool_call", hooks.post_tool_call)


def main() -> None:
    print("hermes-evenhub-bridge: run via Hermes (kind: platform plugin).")
