"""__version__ is load-bearing — it builds the sidecar release URL
(sidecar-v<version>). Guard that every place the version is declared agrees, so a
bump can't silently ship a 404ing download or a mislabeled plugin."""
import json
import re
from pathlib import Path

import hermes_evenhub_bridge as pkg

_ROOT = Path(__file__).parent.parent
_PKG = _ROOT


def test_all_version_declarations_agree():
    v = pkg.__version__
    assert f'version = "{v}"' in (_ROOT / "pyproject.toml").read_text()
    assert f"version: {v}" in (_PKG / "plugin.yaml").read_text()
    manifest = json.loads((_PKG / "dashboard" / "manifest.json").read_text())
    assert manifest["version"] == v


def _names(specs) -> set:
    return {re.split(r"[<>=!~ ]", s.strip())[0] for s in specs if s.strip()
            and not s.strip().startswith("#")}


def test_requirements_match_pyproject_runtime_deps():
    """_bootstrap installs from requirements.txt; it must not drift from the
    canonical [project.dependencies] in pyproject.toml."""
    pyproject = (_ROOT / "pyproject.toml").read_text()
    m = re.search(r"\ndependencies = \[(.*?)\]", pyproject, re.S)
    assert m, "could not find [project].dependencies in pyproject.toml"
    proj = _names(re.findall(r'"([^"]+)"', m.group(1)))
    req = _names((_PKG / "requirements.txt").read_text().splitlines())
    assert proj == req, f"pyproject {proj} != requirements.txt {req}"
