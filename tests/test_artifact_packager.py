"""Tests for Automated Artifact Checkpoint Packager and Manifest Signer."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
import pytest

from courier_core.artifact_packager import (
    ArtifactPackager,
    PackageSummary,
    VerificationReport,
    pack_checkpoint,
    verify_checkpoint,
    main,
)


def create_sample_artifacts(base_dir: Path) -> dict[str, str]:
    sub = base_dir / "src"
    sub.mkdir(parents=True, exist_ok=True)
    f1 = base_dir / "result.txt"
    f1.write_text("Execution result payload", encoding="utf-8")
    f2 = sub / "module.py"
    f2.write_text("def run(): pass", encoding="utf-8")
    return {"result.txt": f1.name, "src/module.py": f2.name}


def test_pack_and_verify_valid_checkpoint(tmp_path):
    source_dir = tmp_path / "artifacts"
    source_dir.mkdir()
    create_sample_artifacts(source_dir)

    pkg_zip = tmp_path / "checkpoint_P26.zip"
    secret = "checkpoint-secret-key-2026"

    packager = ArtifactPackager(secret_key=secret)
    summary = packager.pack(
        source_dir=str(source_dir),
        output_path=str(pkg_zip),
        item_id="P26",
    )

    assert summary.item_id == "P26"
    assert summary.file_count == 2
    assert summary.package_path == str(pkg_zip)
    assert pkg_zip.exists()

    # Verify checkpoint
    report = packager.verify(str(pkg_zip))
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.verified_files_count == 2


def test_tampered_file_fails_verification(tmp_path):
    source_dir = tmp_path / "artifacts"
    source_dir.mkdir()
    create_sample_artifacts(source_dir)

    pkg_zip = tmp_path / "checkpoint.zip"
    secret = "checkpoint-secret-key-2026"

    packager = ArtifactPackager(secret_key=secret)
    packager.pack(source_dir=str(source_dir), output_path=str(pkg_zip), item_id="P26")

    # Tamper with a file inside the zip without updating manifest
    tampered_zip = tmp_path / "checkpoint_tampered.zip"
    with zipfile.ZipFile(pkg_zip, "r") as zin:
        with zipfile.ZipFile(tampered_zip, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "result.txt":
                    data = b"TAMPERED MALICIOUS CONTENT"
                zout.writestr(item, data)

    report = packager.verify(str(tampered_zip))
    assert report.is_valid is False
    assert any("CONTENT_HASH_MISMATCH" in err for err in report.errors)


def test_tampered_manifest_fails_signature(tmp_path):
    source_dir = tmp_path / "artifacts"
    source_dir.mkdir()
    create_sample_artifacts(source_dir)

    pkg_zip = tmp_path / "checkpoint.zip"
    secret = "checkpoint-secret-key-2026"

    packager = ArtifactPackager(secret_key=secret)
    packager.pack(source_dir=str(source_dir), output_path=str(pkg_zip), item_id="P26")

    tampered_zip = tmp_path / "checkpoint_tampered_manifest.zip"
    with zipfile.ZipFile(pkg_zip, "r") as zin:
        with zipfile.ZipFile(tampered_zip, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "manifest.json":
                    manifest_data = json.loads(data.decode("utf-8"))
                    manifest_data["item_id"] = "P99_SPOOFED"
                    data = json.dumps(manifest_data).encode("utf-8")
                zout.writestr(item, data)

    report = packager.verify(str(tampered_zip))
    assert report.is_valid is False
    assert any("SIGNATURE_MISMATCH" in err for err in report.errors)


def test_path_traversal_detection(tmp_path):
    evil_zip = tmp_path / "evil.zip"
    secret = "secret"
    packager = ArtifactPackager(secret_key=secret)

    with zipfile.ZipFile(evil_zip, "w") as zf:
        zf.writestr("../../../evil.bat", "calc.exe")
        zf.writestr("manifest.json", "{}")
        zf.writestr("signature.json", '{"signature": "none"}')

    report = packager.verify(str(evil_zip))
    assert report.is_valid is False
    assert any("PATH_TRAVERSAL_DETECTED" in err for err in report.errors)


def test_wrong_key_fails_verification(tmp_path):
    source_dir = tmp_path / "artifacts"
    source_dir.mkdir()
    create_sample_artifacts(source_dir)

    pkg_zip = tmp_path / "checkpoint.zip"
    packager_legit = ArtifactPackager(secret_key="legit-key")
    packager_legit.pack(source_dir=str(source_dir), output_path=str(pkg_zip), item_id="P26")

    packager_fake = ArtifactPackager(secret_key="attacker-key")
    report = packager_fake.verify(str(pkg_zip))
    assert report.is_valid is False
    assert any("SIGNATURE_MISMATCH" in err for err in report.errors)


def test_cli_invocation_pack_and_verify(tmp_path):
    source_dir = tmp_path / "cli_artifacts"
    source_dir.mkdir()
    create_sample_artifacts(source_dir)

    pkg_zip = tmp_path / "cli_checkpoint.zip"

    # 1. Pack
    code_pack = main([
        "pack",
        "--source", str(source_dir),
        "--output", str(pkg_zip),
        "--item", "P26_cli",
        "--key", "cli-test-key",
    ])
    assert code_pack == 0
    assert pkg_zip.exists()

    # 2. Verify
    code_verify = main([
        "verify",
        "--package", str(pkg_zip),
        "--key", "cli-test-key",
    ])
    assert code_verify == 0
