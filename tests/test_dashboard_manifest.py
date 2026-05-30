import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent


def test_manifest_shape():
    m = json.loads((_ROOT / "dashboard/manifest.json").read_text())
    assert m["name"] == "hermes-evenhub-bridge"
    assert m["tab"]["path"] == "/even-g2"
    assert m["entry"] == "dist/index.js"
    assert m["api"] == "plugin_api.py"


def test_entry_bundle_exists_and_registers():
    js = (_ROOT / "dashboard/dist/index.js").read_text()
    assert "__HERMES_PLUGINS__" in js
    assert "register(" in js
