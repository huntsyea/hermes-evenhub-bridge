from hermes_evenhub_bridge.asr.state import get_active, set_active


def test_set_then_get(tmp_path):
    p = tmp_path / "asr.json"
    set_active("parakeet-tdt-0.6b-v2", p)
    assert get_active(p) == "parakeet-tdt-0.6b-v2"


def test_missing_file_returns_none(tmp_path):
    assert get_active(tmp_path / "absent.json") is None


def test_corrupt_file_returns_none(tmp_path):
    p = tmp_path / "asr.json"
    p.write_text("{not json")
    assert get_active(p) is None
