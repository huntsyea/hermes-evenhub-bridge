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
    assert "ws://host.ts.net:8765" in capsys.readouterr().out


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
