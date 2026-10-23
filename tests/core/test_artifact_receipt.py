"""Tests for Artifact Receipt & Integrity Verification (User Acceptance Requirement 02)."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from courier_core.artifact_receipt import (
    STATUS_EXTERNAL_PRODUCED,
    STATUS_HASH_MISMATCH,
    STATUS_MISSING_DATA,
    STATUS_VERIFIED_MATCH,
    derive_integrity_status,
    format_fingerprint,
    format_size,
    generate_artifact_receipt,
    verify_artifact_receipt,
)
from scripts.artifact_store import ArtifactStore


def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1536) == "1.5 KB"
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(2.5 * 1024 * 1024) == "2.5 MB"
    assert format_size(1024 * 1024 * 1024) == "1.0 GB"
    assert format_size(None) == "unknown"
    assert format_size(-1) == "unknown"
    assert format_size("not-a-number") == "unknown"


def test_format_size_bool_is_unknown():
    assert format_size(True) == "unknown"
    assert format_size(False) == "unknown"


def test_format_fingerprint():
    full_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert format_fingerprint(full_sha) == "e3b0c442...7852b855"
    assert format_fingerprint(None) == "unknown"
    assert format_fingerprint("short") == "unknown"
    assert format_fingerprint("12345") == "unknown"


def test_derive_integrity_status():
    data = b"Hello, Courier Artifact World!"
    sha = hashlib.sha256(data).hexdigest()
    record = {"name": "hello.txt", "size": len(data), "sha256": sha}

    # Missing record
    assert derive_integrity_status(None) == STATUS_MISSING_DATA
    assert derive_integrity_status({}) == STATUS_MISSING_DATA

    proof = {"verification": {"verdict": "PASS", "resolution": "verified"}}

    # Matching bytes without a verdict and resolution are not verified.
    assert derive_integrity_status(record, blob_bytes=data) == STATUS_MISSING_DATA
    assert derive_integrity_status(record, task=proof, blob_bytes=data) == STATUS_VERIFIED_MATCH

    # Mismatched blob bytes
    assert derive_integrity_status(record, blob_bytes=b"corrupt") == STATUS_HASH_MISMATCH

    # Expected sha matches the record only together with bytes and a resolution.
    task_match = {"expected_sha256": sha}
    assert derive_integrity_status(record, task=task_match) == STATUS_MISSING_DATA
    assert derive_integrity_status(record, task=task_match, blob_bytes=data) == STATUS_MISSING_DATA
    task_match_proved = {"expected_sha256": sha, **proof}
    assert derive_integrity_status(record, task=task_match_proved, blob_bytes=data) == STATUS_VERIFIED_MATCH

    # Expected sha in task mismatching
    task_mismatch = {"expected_sha256": "0" * 64}
    assert derive_integrity_status(record, task=task_mismatch) == STATUS_HASH_MISMATCH

    # External task source still needs the bytes and an accepted resolution.
    task_ext = {"source": "external"}
    assert derive_integrity_status(record, task=task_ext) == STATUS_MISSING_DATA
    assert derive_integrity_status(record, task=task_ext, blob_bytes=data) == STATUS_MISSING_DATA
    task_ext_proved = {"source": "external", **proof}
    assert derive_integrity_status(record, task=task_ext_proved, blob_bytes=data) == STATUS_EXTERNAL_PRODUCED

    # A stored hash, a claimed PASS, a missing resolution, or a FAIL on matching
    # bytes is not a verified proof and is not relabeled as a hash mismatch.
    assert derive_integrity_status(record) == STATUS_MISSING_DATA
    assert derive_integrity_status(record, task={}) == STATUS_MISSING_DATA
    assert derive_integrity_status(record, task={"verification": {"verdict": "PASS"}}) == STATUS_MISSING_DATA
    assert derive_integrity_status(record, task={"verification": {}}) == STATUS_MISSING_DATA
    assert derive_integrity_status(
        record,
        task={"verification": {"verdict": "FAIL", "resolution": "verified"}},
        blob_bytes=data,
    ) == STATUS_MISSING_DATA
    assert derive_integrity_status(record, blob_bytes="not-bytes") == STATUS_MISSING_DATA


def test_generate_artifact_receipt_with_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(tmpdir)
        data = b"Report content for Courier"
        sha = hashlib.sha256(data).hexdigest()
        binding = {
            "goal_id": "goal-1",
            "task_id": "task-1",
            "attempt_id": "att-1",
            "dispatch_id": "disp-1",
            "worker_id": "worker-1",
        }
        record = store.put(data, name="report.txt", binding=binding)
        artifact_id = record["artifact_id"]

        receipt = generate_artifact_receipt(artifact_id, store=store)
        assert receipt["artifact_id"] == artifact_id
        assert receipt["name"] == "report.txt"
        assert receipt["size_bytes"] == len(data)
        assert receipt["sha256"] == sha
        assert receipt["sha256_fingerprint"] == f"{sha[:8]}...{sha[-8:]}"
        assert receipt["integrity_status"] == STATUS_MISSING_DATA
        assert receipt["is_valid"] is False
        assert receipt["verification_verdict"] == "FAIL"
        assert receipt["provenance"]["task_id"] == "task-1"
        assert receipt["provenance"]["worker_id"] == "worker-1"
        assert receipt["file_access"]["download_url"] == f"/artifacts/{artifact_id}"
        assert "verified authentic" not in receipt["human_summary"]

        accepted = generate_artifact_receipt(
            artifact_id,
            store=store,
            task={"verification": {"verdict": "PASS", "resolution": "verified"}},
        )
        assert accepted["integrity_status"] == STATUS_VERIFIED_MATCH
        assert accepted["is_valid"] is True
        assert accepted["verification_verdict"] == "PASS"
        assert "verified authentic" in accepted["human_summary"]


def test_hash_mismatch_does_not_publish_pass():
    data = b"Hello, Courier Artifact World!"
    sha = hashlib.sha256(data).hexdigest()
    record = {"name": "hello.txt", "size": len(data), "sha256": sha}
    receipt = generate_artifact_receipt(
        "art-" + sha,
        record=record,
        blob_bytes=b"corrupt",
        task={"verification": {"verdict": "PASS"}},
    )
    assert receipt["integrity_status"] == STATUS_HASH_MISMATCH
    assert receipt["is_valid"] is False
    assert receipt["verification_verdict"] == "FAIL"


def test_missing_bytes_and_missing_verdict_do_not_pass():
    data = b"Hello, Courier Artifact World!"
    sha = hashlib.sha256(data).hexdigest()
    record = {"name": "hello.txt", "size": len(data), "sha256": sha}

    missing_blob = generate_artifact_receipt(
        "art-" + sha,
        record=record,
        task={"verification": {"verdict": "PASS"}},
    )
    unresolved = generate_artifact_receipt(
        "art-" + sha,
        record=record,
        blob_bytes=data,
        task={"verification": {}},
    )

    assert missing_blob["integrity_status"] == STATUS_MISSING_DATA
    assert missing_blob["is_valid"] is False
    assert missing_blob["verification_verdict"] == "FAIL"
    assert unresolved["integrity_status"] == STATUS_MISSING_DATA
    assert unresolved["is_valid"] is False
    assert unresolved["verification_verdict"] == "FAIL"


def test_generate_artifact_receipt_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(tmpdir)
        receipt = generate_artifact_receipt("art-" + "0" * 64, store=store)
        assert receipt["integrity_status"] == STATUS_MISSING_DATA
        assert receipt["is_valid"] is False
        assert receipt["verification_verdict"] == "FAIL"


def test_verify_artifact_receipt():
    data = b"Some verifiable data"
    receipt = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "provenance": {
            "branch": "integration/v1",
            "source_sha": "0b55fc11be5f6280f2dd6977682cf142106a81e7",
        },
    }
    valid, msg = verify_artifact_receipt(
        receipt,
        data,
        expected_branch="integration/v1",
        expected_source_sha="0b55fc11be5f6280f2dd6977682cf142106a81e7",
    )
    assert valid is True
    assert msg == "VERIFIED"

    valid_branch, msg_branch = verify_artifact_receipt(receipt, data, expected_branch="main")
    assert valid_branch is False
    assert "branch mismatch" in msg_branch

    valid_sha, msg_sha = verify_artifact_receipt(receipt, data, expected_source_sha="deadbeef")
    assert valid_sha is False
    assert "source_sha mismatch" in msg_sha

    valid_corrupt, msg_corrupt = verify_artifact_receipt(receipt, b"Tampered data")
    assert valid_corrupt is False
    assert "mismatch" in msg_corrupt


def test_server_artifact_receipt_endpoint(monkeypatch):
    """Test Flask endpoint /artifacts/<artifact_id>/receipt."""
    from flask import Flask
    from scripts.artifact_store import create_blueprint

    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(tmpdir)
        data = b"Artifact for Flask test"
        sha = hashlib.sha256(data).hexdigest()
        binding = {
            "goal_id": "goal-100",
            "task_id": "task-100",
            "attempt_id": "att-100",
            "dispatch_id": "disp-100",
            "worker_id": "worker-100",
        }
        record = store.put(data, name="output.csv", binding=binding)
        artifact_id = record["artifact_id"]

        def noop_auth(fn):
            return fn

        def mock_lookup(tid):
            return {
                "task_id": tid,
                "goal_id": "goal-100",
                "verification": {"verdict": "PASS", "resolution": "verified"},
            }

        app = Flask(__name__)
        bp = create_blueprint(store, worker_auth=noop_auth, verifier_auth=noop_auth, task_lookup=mock_lookup)
        app.register_blueprint(bp)

        client = app.test_client()

        # Existing artifact
        res = client.get(f"/artifacts/{artifact_id}/receipt")
        assert res.status_code == 200
        body = res.get_json()
        assert body["artifact_id"] == artifact_id
        assert body["name"] == "output.csv"
        assert body["size_bytes"] == len(data)
        assert body["sha256"] == sha
        assert body["integrity_status"] == STATUS_VERIFIED_MATCH
        assert body["verification_verdict"] == "PASS"

        # Non-existing artifact
        res_404 = client.get(f"/artifacts/art-{'f' * 64}/receipt")
        assert res_404.status_code == 404
