"""Hermes plugin entry point for the Even Realities G2 platform adapter."""
from __future__ import annotations

import logging
import os

__version__ = "0.3.0"

log = logging.getLogger("hermes-evenhub-bridge")


def register(ctx) -> None:
    from ._bootstrap import ensure_runtime_deps

    if not ensure_runtime_deps(log, __version__):
        # Deps could not be auto-installed (offline / no pip). Register the
        # platform disabled so the gateway surfaces it as unavailable with a clear
        # reason instead of crashing plugin load on the adapter's import of
        # websockets/numpy.
        def _unavailable_factory(cfg):
            raise RuntimeError(
                "Even Realities G2 dependencies are not installed and could not "
                "be auto-installed. Run: "
                f"{__import__('sys').executable} -m pip install -r "
                "<plugin>/requirements.txt, then restart the gateway.")

        ctx.register_platform(
            name="even_g2",
            label="Even Realities G2",
            adapter_factory=_unavailable_factory,
            check_fn=lambda: False,
            emoji="👓",
            cron_deliver_env_var="EVEN_G2_HOME_CHANNEL",
            platform_hint="",
        )
        return

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
        cron_deliver_env_var="EVEN_G2_HOME_CHANNEL",
        platform_hint=("You are talking to the user through Even Realities G2 "
                       "smart glasses with a tiny display; keep replies short."),
    )
    ctx.register_hook("pre_tool_call", hooks.pre_tool_call)
    ctx.register_hook("post_tool_call", hooks.post_tool_call)


def main() -> None:
    print("hermes-evenhub-bridge: run via Hermes (kind: platform plugin).")
