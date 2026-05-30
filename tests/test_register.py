import pytest as _pytest
_pytest.importorskip("gateway")  # gateway-dependent module
pytestmark = _pytest.mark.gateway

import hermes_evenhub_bridge as pkg


class FakeCtx:
    def __init__(self):
        self.platform = None
        self.hooks = []
        self.cli_commands = {}
    def register_platform(self, **kw):
        self.platform = kw
    def register_hook(self, name, cb):
        self.hooks.append(name)
    def register_cli_command(self, **kw):
        self.cli_commands[kw["name"]] = kw


def test_register_wires_platform_and_hooks():
    ctx = FakeCtx()
    pkg.register(ctx)
    assert ctx.platform["name"] == "even_g2"
    assert ctx.platform["label"] == "Even Realities G2"
    assert callable(ctx.platform["adapter_factory"])
    assert "pre_tool_call" in ctx.hooks
    assert "post_tool_call" in ctx.hooks


def test_adapter_factory_builds_adapter():
    from gateway.config import PlatformConfig
    ctx = FakeCtx()
    pkg.register(ctx)
    adapter = ctx.platform["adapter_factory"](PlatformConfig(extra={}))
    assert adapter.platform.value == "even_g2"


def test_check_fn_requires_token(monkeypatch):
    ctx = FakeCtx()
    pkg.register(ctx)
    check = ctx.platform["check_fn"]
    monkeypatch.delenv("EVENHUB_BRIDGE_TOKEN", raising=False)
    assert check() is False
    monkeypatch.setenv("EVENHUB_BRIDGE_TOKEN", "x")
    assert check() is True


def test_register_sets_cron_deliver_env_var():
    ctx = FakeCtx()
    pkg.register(ctx)
    assert ctx.platform["cron_deliver_env_var"] == "EVEN_G2_HOME_CHANNEL"


def test_register_declares_required_env_and_enablement():
    ctx = FakeCtx()
    pkg.register(ctx)
    assert ctx.platform["required_env"] == ["EVENHUB_BRIDGE_TOKEN"]
    assert callable(ctx.platform["env_enablement_fn"])


def test_register_registers_cli_command():
    ctx = FakeCtx()
    pkg.register(ctx)
    assert "even-g2" in ctx.cli_commands
    cmd = ctx.cli_commands["even-g2"]
    assert callable(cmd["setup_fn"]) and callable(cmd["handler_fn"])
