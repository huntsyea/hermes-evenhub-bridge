"""Test setup for the flat directory-plugin layout.

The package files live at the repo ROOT (so `hermes plugins install` finds
plugin.yaml there), and the repo is not pip-installed as a package. So register
the root as the `hermes_evenhub_bridge` package for imports, and make the Hermes
`gateway` importable (pip-installed in CI, or the local ~/.hermes/hermes-agent
checkout in dev). Tests that need the gateway are marked `@pytest.mark.gateway`.
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

# --- register the repo root as the hermes_evenhub_bridge package ---------------
_ROOT = Path(__file__).resolve().parent.parent
if "hermes_evenhub_bridge" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "hermes_evenhub_bridge",
        str(_ROOT / "__init__.py"),
        submodule_search_locations=[str(_ROOT)],
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hermes_evenhub_bridge"] = mod
    spec.loader.exec_module(mod)

# --- make the Hermes gateway importable ----------------------------------------
# CI installs `hermes-agent` from PyPI (top-level `gateway` package); fall back to
# the locally-installed agent checkout for dev.
try:
    import gateway  # noqa: F401
except ImportError:
    _H = os.environ.get("HERMES_AGENT_ROOT", os.path.expanduser("~/.hermes/hermes-agent"))
    if os.path.isdir(_H) and _H not in sys.path:
        sys.path.insert(0, _H)

# Register the platform so Platform("even_g2") resolves when a gateway-marked test
# constructs EvenG2Adapter directly. If the gateway isn't present, those tests are
# deselected via `-m "not gateway"`.
try:
    from gateway.platform_registry import platform_registry, PlatformEntry

    if not platform_registry.is_registered("even_g2"):
        platform_registry.register(PlatformEntry(
            name="even_g2",
            label="Even Realities G2",
            adapter_factory=lambda cfg: None,
            check_fn=lambda: True,
        ))
except ImportError:
    pass


@pytest.fixture(autouse=True)
def _isolate_home_channel_env():
    """EvenG2Adapter._ensure_home_channel writes EVEN_G2_HOME_CHANNEL into the
    process env on every on_text turn; isolate it so tests don't leak it."""
    key = "EVEN_G2_HOME_CHANNEL"
    saved = os.environ.pop(key, None)
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved
