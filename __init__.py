"""Hermes plugin entry point for the Even Realities G2 platform adapter."""
from __future__ import annotations

import logging
import os
import sys

__version__ = "0.3.0"

log = logging.getLogger("hermes-evenhub-bridge")


def register(ctx) -> None:
    from ._bootstrap import ensure_runtime_deps

    deps_ok = ensure_runtime_deps(log, __version__)

    if deps_ok:
        from .adapter import EvenG2Adapter
        from . import hooks

        def adapter_factory(cfg):
            adapter = EvenG2Adapter(cfg)
            hooks.bind(adapter)
            return adapter

        def check_fn() -> bool:
            return bool(os.environ.get("EVENHUB_BRIDGE_TOKEN"))
    else:
        # Deps couldn't be auto-installed (offline / no pip). Register disabled so
        # the gateway shows the platform as unavailable with a clear reason instead
        # of crashing plugin load on the adapter's import of websockets/numpy.
        def adapter_factory(cfg):
            raise RuntimeError(
                "Even Realities G2 dependencies are not installed and could not be "
                f"auto-installed. Run: {sys.executable} -m pip install -r "
                "<plugin>/requirements.txt, then restart the gateway.")

        def check_fn() -> bool:
            return False

    ctx.register_platform(
        name="even_g2",
        label="Even Realities G2",
        adapter_factory=adapter_factory,
        check_fn=check_fn,
        emoji="👓",
        cron_deliver_env_var="EVEN_G2_HOME_CHANNEL",
        platform_hint=("You are talking to the user through Even Realities G2 "
                       "smart glasses with a tiny display; keep replies short."),
    )
    if deps_ok:
        ctx.register_hook("pre_tool_call", hooks.pre_tool_call)
        ctx.register_hook("post_tool_call", hooks.post_tool_call)


def main() -> None:
    print("hermes-evenhub-bridge: run via Hermes (kind: platform plugin).")
