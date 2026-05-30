import subprocess

import hermes_evenhub_bridge._bootstrap as boot


def test_no_op_when_all_present(monkeypatch):
    monkeypatch.setattr(boot, "_missing_modules", lambda: [])

    def fake_run(*a, **k):
        raise AssertionError("pip must not run when nothing is missing")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert boot.ensure_runtime_deps() is True


def test_installs_missing_with_correct_argv(monkeypatch, tmp_path):
    # First probe reports a missing module; after the install it is present.
    probes = iter([["numpy"], []])
    monkeypatch.setattr(boot, "_missing_modules", lambda: next(probes))
    seen = {}

    def fake_run(argv, **k):
        seen["argv"] = argv

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert boot.ensure_runtime_deps(version="9.9.9") is True
    assert seen["argv"][:4] == [boot.sys.executable, "-m", "pip", "install"]
    assert seen["argv"][-1].endswith("requirements.txt")
    # No cooldown marker on success.
    assert not (tmp_path / "even_g2" / ".deps-failed-9.9.9").exists()


def test_writes_cooldown_marker_when_still_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(boot, "_missing_modules", lambda: ["numpy"])  # never resolves

    def fake_run(argv, **k):
        class R:
            returncode = 1

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert boot.ensure_runtime_deps(version="9.9.9") is False
    assert (tmp_path / "even_g2" / ".deps-failed-9.9.9").exists()


def test_skips_install_when_cooldown_marker_present(monkeypatch, tmp_path):
    monkeypatch.setattr(boot, "_missing_modules", lambda: ["numpy"])
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    marker = tmp_path / "even_g2" / ".deps-failed-9.9.9"
    marker.parent.mkdir(parents=True)
    marker.write_text("install failed")

    def fake_run(*a, **k):
        raise AssertionError("must not re-attempt install while cooldown marker exists")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert boot.ensure_runtime_deps(version="9.9.9") is False


def test_cooldown_marker_is_version_scoped(monkeypatch, tmp_path):
    # A failure marker from a previous version must not block a new version's install.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    old = tmp_path / "even_g2" / ".deps-failed-0.0.1"
    old.parent.mkdir(parents=True)
    old.write_text("old failure")
    probes = iter([["numpy"], []])
    monkeypatch.setattr(boot, "_missing_modules", lambda: next(probes))

    def fake_run(argv, **k):
        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert boot.ensure_runtime_deps(version="9.9.9") is True


def test_never_raises_when_pip_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(boot, "_missing_modules", lambda: ["numpy"])

    def boom(*a, **k):
        raise OSError("pip not found")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert boot.ensure_runtime_deps(version="9.9.9") is False
