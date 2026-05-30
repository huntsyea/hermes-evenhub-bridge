from hermes_evenhub_bridge.__main__ import main
from hermes_evenhub_bridge.asr.state import get_active


def test_set_writes_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    rc = main(["asr", "set", "whisper-tiny"])
    assert rc == 0
    assert get_active(tmp_path / "asr.json") == "whisper-tiny"


def test_set_unknown_name_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    rc = main(["asr", "set", "bogus"])
    assert rc != 0
    assert get_active(tmp_path / "asr.json") is None


def test_list_shows_models(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    rc = main(["asr", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "parakeet-tdt-0.6b-v2" in out and "whisper-tiny" in out


def test_download_calls_ensure(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENHUB_ASR_STATE", str(tmp_path / "asr.json"))
    called = {}
    import hermes_evenhub_bridge.asr as asr

    def fake_build(name, cfg):
        class B:
            def ensure_downloaded(self): called["x"] = name
            def is_installed(self): return False
        return B()

    monkeypatch.setattr(asr, "_build_backend", fake_build)
    rc = main(["asr", "download", "parakeet-tdt-0.6b-v2"])
    assert rc == 0 and called["x"] == "parakeet-tdt-0.6b-v2"
