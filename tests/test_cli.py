import argparse

import hermes_evenhub_bridge.cli as cli


def _parse(argv):
    p = argparse.ArgumentParser()
    cli.setup_parser(p)
    return p.parse_args(argv)


def test_url_dispatch(monkeypatch, capsys):
    from hermes_evenhub_bridge import net
    monkeypatch.setattr(net, "resolve",
                        lambda cfg: ("0.0.0.0", "ws://host.ts.net:8765",
                                     {"magic_dns": "host.ts.net", "ip": "100.1.1.1", "online": True}))
    rc = cli.run(_parse(["url"]))
    assert rc == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "ws://host.ts.net:8765"
    assert "Run `hermes even-g2 setup`" in out


def test_setup_dispatch(monkeypatch, capsys):
    from hermes_evenhub_bridge import setup_flow
    calls = []

    def configure_local_bridge(force_token=False):
        calls.append(force_token)
        return {
            "token_generated": True,
            "token": "generated-token",
            "restart_required": True,
        }

    monkeypatch.setattr(setup_flow, "configure_local_bridge", configure_local_bridge)
    monkeypatch.setattr(setup_flow, "enable_tailscale_serve", lambda serve_port=None: {
        "public_url": "wss://host.ts.net:8443",
    })
    rc = cli.run(_parse(["setup"]))
    out = capsys.readouterr().out
    assert rc == 0
    assert calls == [False]
    assert "generated-token" in out
    assert "App URL: wss://host.ts.net:8443" in out.splitlines()


def test_setup_force_token_dispatch(monkeypatch, capsys):
    from hermes_evenhub_bridge import setup_flow
    calls = []

    def configure_local_bridge(force_token=False):
        calls.append(force_token)
        return {
            "token_generated": True,
            "token": "regenerated-token",
            "restart_required": True,
        }

    monkeypatch.setattr(setup_flow, "configure_local_bridge", configure_local_bridge)
    monkeypatch.setattr(setup_flow, "enable_tailscale_serve", lambda serve_port=None: {
        "public_url": "wss://host.ts.net:8443",
    })
    rc = cli.run(_parse(["setup", "--force-token"]))
    out = capsys.readouterr().out
    assert rc == 0
    assert calls == [True]
    assert "regenerated-token" in out
    assert "App URL: wss://host.ts.net:8443" in out.splitlines()


def test_setup_skip_serve_force_token_dispatch(monkeypatch, capsys):
    from hermes_evenhub_bridge import setup_flow
    calls = []

    def configure_local_bridge(force_token=False):
        calls.append(force_token)
        return {
            "token_generated": True,
            "token": "regenerated-token",
            "restart_required": True,
        }

    def enable_tailscale_serve(serve_port=None):
        raise AssertionError("skip-serve must not enable Tailscale Serve")

    monkeypatch.setattr(setup_flow, "configure_local_bridge", configure_local_bridge)
    monkeypatch.setattr(setup_flow, "enable_tailscale_serve", enable_tailscale_serve)
    rc = cli.run(_parse(["setup", "--skip-serve", "--force-token"]))
    out = capsys.readouterr().out
    assert rc == 0
    assert calls == [True]
    assert "regenerated-token" in out
    assert "App URL:" not in out


def test_asr_list_dispatch(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    rc = cli.run(_parse(["asr", "list"]))
    out = capsys.readouterr().out
    assert rc == 0
    assert "whisper-tiny" in out and "parakeet-tdt-0.6b-v2" in out


def test_asr_set_unknown_is_error(monkeypatch, tmp_path):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    assert cli.run(_parse(["asr", "set", "bogus"])) == 2


def test_no_subcommand_prints_usage(capsys):
    assert cli.run(_parse([])) == 2
    assert "usage" in capsys.readouterr().out
