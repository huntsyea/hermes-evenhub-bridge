from hermes_evenhub_bridge.status import StatusFile


def test_write_then_read_roundtrip(tmp_path):
    sf = StatusFile(tmp_path / "even_g2_status.json")
    sf.update(connected=1, mic="idle", active_session="terminal redesign")
    data = sf.read()
    assert data["connected"] == 1
    assert data["mic"] == "idle"
    assert data["active_session"] == "terminal redesign"
    assert "updated_at" in data


def test_read_missing_returns_defaults(tmp_path):
    sf = StatusFile(tmp_path / "nope.json")
    data = sf.read()
    assert data["connected"] == 0
    assert data["mic"] == "off"
    assert data["public_url"] == ""
    assert data["local_url"] == ""
    assert data["serve_port"] == 8443
