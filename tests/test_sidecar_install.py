import hashlib
import os
from pathlib import Path

import hermes_evenhub_bridge.asr.sidecar_install as si


def test_skips_when_unsupported_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(si, "is_supported_platform", lambda: False)
    dest = tmp_path / "bin" / "g2-asr-sidecar"
    assert si.ensure_sidecar_binary("0.3.0", str(dest)) is None
    assert not dest.exists()


def test_returns_existing_executable_without_download(monkeypatch, tmp_path):
    dest = tmp_path / "g2-asr-sidecar"
    dest.write_bytes(b"x")
    dest.chmod(0o755)
    monkeypatch.setattr(si, "is_supported_platform", lambda: True)

    def boom(*a, **k):
        raise AssertionError("must not download when binary already present")

    monkeypatch.setattr(si, "_download", boom)
    monkeypatch.setattr(si, "_stream_to_file", boom)
    assert si.ensure_sidecar_binary("0.3.0", str(dest)) == str(dest)


def _checksum_bytes(blob: bytes) -> bytes:
    return (hashlib.sha256(blob).hexdigest() + "  " + si.ASSET_NAME + "\n").encode()


def test_downloads_verifies_and_chmods(monkeypatch, tmp_path):
    monkeypatch.setattr(si, "is_supported_platform", lambda: True)
    blob = b"BINARYDATA"
    urls = []

    def fake_dl(url, timeout=30.0):
        urls.append(url)
        return _checksum_bytes(blob)

    def fake_stream(url, dest_tmp, timeout=300.0):
        urls.append(url)
        Path(dest_tmp).write_bytes(blob)
        return hashlib.sha256(blob).hexdigest()

    monkeypatch.setattr(si, "_download", fake_dl)
    monkeypatch.setattr(si, "_stream_to_file", fake_stream)
    monkeypatch.setattr(si, "_dequarantine", lambda p: None)
    monkeypatch.setattr(si, "_verify_signature", lambda p, log=None: True)

    dest = tmp_path / "bin" / "g2-asr-sidecar"
    got = si.ensure_sidecar_binary("0.3.0", str(dest))
    assert got == str(dest)
    assert dest.read_bytes() == blob
    assert os.access(dest, os.X_OK)
    assert any("sidecar-v0.3.0/" + si.ASSET_NAME in u for u in urls)


def test_rejects_invalid_signature(monkeypatch, tmp_path):
    monkeypatch.setattr(si, "is_supported_platform", lambda: True)
    blob = b"BINARYDATA"
    monkeypatch.setattr(si, "_download", lambda url, timeout=30.0: _checksum_bytes(blob))

    def fake_stream(url, dest_tmp, timeout=300.0):
        Path(dest_tmp).write_bytes(blob)
        return hashlib.sha256(blob).hexdigest()

    monkeypatch.setattr(si, "_stream_to_file", fake_stream)
    # Checksum matches but the signature doesn't verify → refuse + clean up.
    monkeypatch.setattr(si, "_verify_signature", lambda p, log=None: False)
    dest = tmp_path / "bin" / "g2-asr-sidecar"
    assert si.ensure_sidecar_binary("0.3.0", str(dest)) is None
    assert not dest.exists()
    assert not (dest.parent / "g2-asr-sidecar.tmp").exists()


def test_verify_signature_disabled_by_empty_team(monkeypatch):
    monkeypatch.setenv("EVENHUB_ASR_SIDECAR_TEAM_ID", "")
    # No codesign call should happen when the team check is disabled.
    monkeypatch.setattr(si.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no codesign")))
    assert si._verify_signature(object()) is True


def test_checksum_mismatch_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(si, "is_supported_platform", lambda: True)
    monkeypatch.setattr(si, "_download",
                        lambda url, timeout=30.0: b"deadbeef  " + si.ASSET_NAME.encode())

    def fake_stream(url, dest_tmp, timeout=300.0):
        Path(dest_tmp).write_bytes(b"BINARYDATA")
        return hashlib.sha256(b"BINARYDATA").hexdigest()

    monkeypatch.setattr(si, "_stream_to_file", fake_stream)
    dest = tmp_path / "bin" / "g2-asr-sidecar"
    assert si.ensure_sidecar_binary("0.3.0", str(dest)) is None
    assert not dest.exists()
    # The partial temp file is cleaned up.
    assert not (dest.parent / "g2-asr-sidecar.tmp").exists()


def test_missing_checksum_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(si, "is_supported_platform", lambda: True)

    def boom_dl(url, timeout=30.0):
        raise OSError("404")  # checksum unavailable

    def no_stream(*a, **k):
        raise AssertionError("must not stream the binary without a checksum")

    monkeypatch.setattr(si, "_download", boom_dl)
    monkeypatch.setattr(si, "_stream_to_file", no_stream)
    dest = tmp_path / "bin" / "g2-asr-sidecar"
    assert si.ensure_sidecar_binary("0.3.0", str(dest)) is None
    assert not dest.exists()


def test_release_base_honors_repo_override(monkeypatch):
    monkeypatch.setenv("EVENHUB_ASR_SIDECAR_REPO", "acme/fork")
    assert "acme/fork/releases/download/sidecar-v0.3.0" in si._release_base("0.3.0")


def test_never_raises_on_download_error(monkeypatch, tmp_path):
    monkeypatch.setattr(si, "is_supported_platform", lambda: True)
    monkeypatch.setattr(si, "_download",
                        lambda url, timeout=30.0: _checksum_bytes(b"x"))

    def boom_stream(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(si, "_stream_to_file", boom_stream)
    dest = tmp_path / "bin" / "g2-asr-sidecar"
    assert si.ensure_sidecar_binary("0.3.0", str(dest)) is None
