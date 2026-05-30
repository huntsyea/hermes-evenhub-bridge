import json
from hermes_evenhub_bridge.status import StatusFile


def test_status_carries_asr_fields(tmp_path):
    sf = StatusFile(tmp_path / "status.json")
    sf.update(asr_active="parakeet-tdt-0.6b-v2",
              asr_models=[{"name": "whisper-tiny", "installed": True}])
    data = json.loads((tmp_path / "status.json").read_text())
    assert data["asr_active"] == "parakeet-tdt-0.6b-v2"
    assert data["asr_models"][0]["name"] == "whisper-tiny"
