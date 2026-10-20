from __future__ import annotations
import os

import json
import subprocess
import sys
from pathlib import Path

import pytest

from courier_core.artifact_verifier import verify_artifacts, ArtifactVerificationReport


def test_verify_artifacts_happy_path_no_manifest(tmp_path: Path):
    d = tmp_path / "artifacts"
    d.mkdir()
    f1 = d / "out.txt"
    f1.write_text("hello world", encoding="utf-8")
    sub = d / "sub"
    sub.mkdir()
    f2 = sub / "data.bin"
    f2.write_bytes(b"\x00\x01\x02\x03")

    report = verify_artifacts(d)
    assert isinstance(report, ArtifactVerificationReport)
    assert report.valid is True
    assert report.checked_count == 2
    assert report.total_bytes == len("hello world".encode("utf-8")) + 4
    assert "out.txt" in report.artifacts
    assert "sub/data.bin" in report.artifacts
    assert len(report.tampered) == 0
    assert len(report.missing) == 0
    assert len(report.escaped) == 0


def test_verify_artifacts_happy_path_with_manifest(tmp_path: Path):
    import hashlib

    d = tmp_path / "artifacts"
    d.mkdir()
    f1 = d / "model.onnx"
    f1.write_bytes(b"dummy model data")
    expected_sha = hashlib.sha256(b"dummy model data").hexdigest()

    manifest = {
        "artifacts": {
            "model.onnx": {"sha256": expected_sha, "size_bytes": len(b"dummy model data")}
        }
    }

    report = verify_artifacts(d, manifest=manifest)
    assert report.valid is True
    assert report.checked_count == 1
    assert len(report.tampered) == 0
    assert len(report.missing) == 0


def test_verify_artifacts_detects_tampered_content(tmp_path: Path):
    d = tmp_path / "artifacts"
    d.mkdir()
    f1 = d / "output.csv"
    f1.write_text("tampered content", encoding="utf-8")

    manifest = {
        "artifacts": {
            "output.csv": {"sha256": "0" * 64, "size_bytes": 100}
        }
    }

    report = verify_artifacts(d, manifest=manifest)
    assert report.valid is False
    assert "output.csv" in report.tampered


def test_verify_artifacts_detects_missing_file(tmp_path: Path):
    d = tmp_path / "artifacts"
    d.mkdir()

    manifest = {
        "artifacts": {
            "missing.txt": {"sha256": "abcdef", "size_bytes": 10}
        }
    }

    report = verify_artifacts(d, manifest=manifest)
    assert report.valid is False
    assert "missing.txt" in report.missing


def test_verify_artifacts_detects_traversal_attack(tmp_path: Path):
    d = tmp_path / "artifacts"
    d.mkdir()
    outside = tmp_path / "secret.key"
    outside.write_text("secret", encoding="utf-8")

    manifest = {
        "artifacts": {
            "../secret.key": {"sha256": "any", "size_bytes": 6}
        }
    }

    report = verify_artifacts(d, manifest=manifest)
    assert report.valid is False
    assert any("../secret.key" in esc for esc in report.escaped)


def test_verify_artifacts_nonexistent_root_dir(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist"
    report = verify_artifacts(nonexistent)
    assert report.valid is False
    assert len(report.errors) > 0


def test_verify_artifacts_read_only_never_mutates(tmp_path: Path):
    d = tmp_path / "artifacts"
    d.mkdir()
    f1 = d / "proof.txt"
    f1.write_text("immutable", encoding="utf-8")

    before_mtime = f1.stat().st_mtime
    before_entries = list(d.iterdir())

    report = verify_artifacts(d)
    assert report.valid is True

    after_mtime = f1.stat().st_mtime
    after_entries = list(d.iterdir())

    assert before_mtime == after_mtime
    assert before_entries == after_entries


def test_cli_invocation_happy_and_tampered(tmp_path: Path):
    import hashlib

    d = tmp_path / "artifacts"
    d.mkdir()
    f1 = d / "data.json"
    content = b'{"status": "ok"}'
    f1.write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()

    mf_path = tmp_path / "manifest.json"
    mf_path.write_text(json.dumps({"artifacts": {"data.json": {"sha256": sha}}}), encoding="utf-8")

    root = str(Path(__file__).resolve().parent.parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = root

    # Happy path
    res = subprocess.run(
        [sys.executable, "-m", "courier_core.artifact_verifier", str(d), "--manifest", str(mf_path)],
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert payload["valid"] is True
    assert payload["checked_count"] == 1

    # Tampered path
    f1.write_bytes(b'{"status": "tampered"}')
    res_tampered = subprocess.run(
        [sys.executable, "-m", "courier_core.artifact_verifier", str(d), "--manifest", str(mf_path)],
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert res_tampered.returncode == 1
    payload_tampered = json.loads(res_tampered.stdout)
    assert payload_tampered["valid"] is False
    assert "data.json" in payload_tampered["tampered"]
