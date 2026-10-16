"""Deterministic offline tests for Seed 021 / Catalog 0206: Alter Testartefakte klären.

Validates fail-closed handling of stale, unknown, corrupted, or replayed test artifacts:
- Positive case: Fresh, valid artifact in the content-addressed store is verified and readable.
- Negative case 1 (FAIL-CLOSED): Unknown or expired artifact_id raises ArtifactError('unknown artifact_id').
- Negative case 2 (FAIL-CLOSED): Stale blob file missing or deleted raises ArtifactError('artifact bytes missing').
- Negative case 3 (FAIL-CLOSED): Tampered or corrupted blob on disk is detected via SHA256 mismatch.
- Negative case 4 (FAIL-CLOSED): Replaying an old artifact from another task fails check_reference with binding mismatch.
- Negative case 5 (FAIL-CLOSED): Verifier rejects stale or tampered artifact data without trusting worker claims.
"""
import hashlib
import json
import pytest
from pathlib import Path

from scripts.artifact_store import (
    ArtifactError,
    ArtifactStore,
    verify_uploaded_artifact,
)

BINDING_TASK_A = {
    "goal_id": "goal-021",
    "task_id": "task-021-a",
    "attempt_id": "attempt-1",
    "dispatch_id": "dispatch-01",
    "worker_id": "WINDOWS-01",
}

BINDING_TASK_B = {
    "goal_id": "goal-021",
    "task_id": "task-021-b",
    "attempt_id": "attempt-1",
    "dispatch_id": "dispatch-02",
    "worker_id": "WINDOWS-01",
}


def test_positive_fresh_valid_artifact_readable_and_verified(tmp_path):
    """Positivfall: Fresh, authorized test artifact is stored, retrieved, and verified."""
    store = ArtifactStore(tmp_path / "artifacts")
    payload = b"fresh valid test artifact payload\n"
    record = store.put(payload, name="test_output.json", binding=BINDING_TASK_A)

    assert record["name"] == "test_output.json"
    assert record["sha256"] == hashlib.sha256(payload).hexdigest()
    assert store.read_bytes(record["artifact_id"]) == payload

    ref = {
        "path": "test_output.json",
        "sha256": record["sha256"],
        "artifact_id": record["artifact_id"],
        "size": len(payload),
    }
    store.check_reference(ref, BINDING_TASK_A)
    ok, reason = verify_uploaded_artifact(payload, record, ref, BINDING_TASK_A)
    assert ok is True
    assert reason == "ok"


def test_negative_unknown_or_expired_artifact_id_fails_closed(tmp_path):
    """Synthetischer Negativfall 1: Querying an unknown or expired artifact fails closed."""
    store = ArtifactStore(tmp_path / "artifacts")
    stale_artifact_id = "art-" + "0" * 64

    # Record lookup returns None
    assert store.get_record(stale_artifact_id) is None

    # Byte read fails closed with ArtifactError
    with pytest.raises(ArtifactError, match="unknown artifact_id"):
        store.read_bytes(stale_artifact_id)

    # Reference check fails closed
    fake_ref = {
        "path": "test.txt",
        "sha256": "0" * 64,
        "artifact_id": stale_artifact_id,
    }
    with pytest.raises(ArtifactError, match="unknown artifact_id"):
        store.check_reference(fake_ref, BINDING_TASK_A)


def test_negative_stale_missing_blob_fails_closed(tmp_path):
    """Synthetischer Negativfall 2: Expired/pruned blob with orphaned record fails closed."""
    store = ArtifactStore(tmp_path / "artifacts")
    payload = b"payload to be pruned"
    record = store.put(payload, name="temp.log", binding=BINDING_TASK_A)

    # Simulate blob file pruned/deleted while record remains
    blob_path = store._blob_path(record["sha256"])
    assert blob_path.exists()
    blob_path.unlink()

    with pytest.raises(ArtifactError, match="artifact bytes missing"):
        store.read_bytes(record["artifact_id"])


def test_negative_corrupted_blob_on_disk_fails_closed(tmp_path):
    """Synthetischer Negativfall 3: Tampered or bit-rotted blob on disk is detected fail-closed."""
    store = ArtifactStore(tmp_path / "artifacts")
    payload = b"clean original data"
    record = store.put(payload, name="result.bin", binding=BINDING_TASK_A)

    # Corrupt the underlying blob on disk
    blob_path = store._blob_path(record["sha256"])
    blob_path.write_bytes(b"corrupted altered data bytes!!")

    with pytest.raises(ArtifactError, match="stored blob is corrupt"):
        store.put(payload, name="result.bin", binding=BINDING_TASK_A)


def test_negative_replayed_old_artifact_from_foreign_task_fails_closed(tmp_path):
    """Synthetischer Negativfall 4: Replaying an old artifact from a different task is rejected."""
    store = ArtifactStore(tmp_path / "artifacts")
    payload = b"artifact created for Task A"
    record = store.put(payload, name="output.txt", binding=BINDING_TASK_A)

    # Worker attempts to submit Task A's artifact reference for Task B
    stale_replayed_ref = {
        "path": "output.txt",
        "sha256": record["sha256"],
        "artifact_id": record["artifact_id"],
        "size": len(payload),
    }

    with pytest.raises(ArtifactError, match="artifact task_id mismatch"):
        store.check_reference(stale_replayed_ref, BINDING_TASK_B)


def test_negative_verifier_rejects_tampered_stale_artifact_fail_closed(tmp_path):
    """Synthetischer Negativfall 5: Independent verifier detects content mismatch fail-closed."""
    payload = b"original server artifact"
    sha = hashlib.sha256(payload).hexdigest()
    record = {
        "artifact_id": "art-" + "1" * 64,
        "name": "data.csv",
        "sha256": sha,
        "size": len(payload),
        **BINDING_TASK_A,
    }
    ref = {
        "path": "data.csv",
        "sha256": sha,
        "artifact_id": record["artifact_id"],
        "size": len(payload),
    }

    # Stale/tampered payload offered to verifier
    tampered_data = b"tampered data with wrong sha"
    ok, reason = verify_uploaded_artifact(tampered_data, record, ref, BINDING_TASK_A)
    assert ok is False
    assert reason == "hash mismatch"


def test_persistence_and_restart_idempotency_after_reload(tmp_path):
    """Persistenz- und Restart-Nachweis: Stored artifacts are reproducible across reloads and idempotent."""
    store_dir = tmp_path / "artifacts"
    store_initial = ArtifactStore(store_dir)
    payload = b"durable artifact payload preserved across restart"
    record1 = store_initial.put(payload, name="durable.txt", binding=BINDING_TASK_A)
    artifact_id = record1["artifact_id"]

    # Process reload / restart: fresh ArtifactStore instance reading from the exact same disk root
    store_reloaded = ArtifactStore(store_dir)

    # 1. State is durable and unchanged
    record_reloaded = store_reloaded.get_record(artifact_id)
    assert record_reloaded == record1
    assert store_reloaded.read_bytes(artifact_id) == payload

    # 2. Idempotent re-put: exactly the same artifact_id and record, no duplication
    record2 = store_reloaded.put(payload, name="durable.txt", binding=BINDING_TASK_A)
    assert record2["artifact_id"] == artifact_id
    assert record2 == record1

    # 3. Conflict detection on restart: attempting to reuse same id with altered metadata raises ArtifactError
    conflicting_binding = dict(BINDING_TASK_A, worker_id="WINDOWS-02")
    # art id for different binding is different, but if someone tries to forge record:
    rec_path = store_reloaded._record_path(artifact_id)
    # Ensure conflict check in put() works if record file exists with mismatch
    with pytest.raises(ArtifactError, match="artifact record conflict"):
        # Temporarily tamper the record to verify fail-closed reload behavior
        tampered_rec = dict(record1, worker_id="WINDOWS-FORGED")
        rec_path.write_text(json.dumps(tampered_rec), encoding="utf-8")
        store_reloaded.put(payload, name="durable.txt", binding=BINDING_TASK_A)

