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


def test_entry_bundle_fetches_gateway_status_and_reports_errors():
    js = (_ROOT / "dashboard/dist/index.js").read_text()
    assert "SDK.api.getStatus" in js or 'fetchJSON("/api/status")' in js
    assert "data.gateway_platforms || data.platforms" in js
    assert ".catch(function () {})" not in js
    assert "ErrorLine" in js
    assert "!model.installed && isDownloading" not in js
    assert "Install sidecar" in js
    assert "No transcription models found." in js
    assert "toneColor" in js
    assert "shortPath" in js


def test_entry_uses_sdk_api_base():
    js = (_ROOT / "dashboard/dist/index.js").read_text()
    assert "SDK.api" in js
    assert (
        '(typeof SDK.api === "string" ? SDK.api : "/api/plugins/hermes-evenhub-bridge")'
        '.replace(/\\/$/, "")' in js
    )


def test_entry_supports_token_regeneration():
    js = (_ROOT / "dashboard/dist/index.js").read_text()
    assert "Generate token" in js
    assert "Regenerate token" in js
    assert "force_token" in js
    assert "window.confirm" in js
    assert "Regenerating replaces the phone-app token after Hermes Gateway restarts." in js
    assert "Local bridge settings saved. Existing token unchanged." in js
