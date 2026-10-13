"""Catalog 2126-2150: task-owned artifact expectations fail closed.

A worker result that omits a named task expectation must not PASS.
Dict-shaped task artifacts must not raise; malformed entries FAIL.
Worker-supplied expected_sha256 on the result does not satisfy the task.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from scripts.courier_verifier import verify_artifacts

HELLO = hashlib.sha256(b"hello").hexdigest()


def _local_ok(_path, _sha):
    return True


def test_named_expected_artifacts_omission_fails():
    task = {
        "target_agent": "linux-worker",
        "expected_artifacts": {"needed.txt": HELLO},
    }
    result = {"artifacts": [{"path": "other.txt", "sha256": HELLO, "expected_sha256": HELLO}]}
    assert verify_artifacts(task, result, local_verify=_local_ok) == "FAIL"


def test_dict_shaped_task_artifacts_omission_fails_without_raising():
    task = {
        "target_agent": "linux-worker",
        "artifacts": [{"path": "needed.txt", "expected_sha256": HELLO}],
    }
    result = {"artifacts": [{"path": "other.txt", "sha256": HELLO}]}
    assert verify_artifacts(task, result, local_verify=_local_ok) == "FAIL"


def test_malformed_task_artifact_entry_fails_closed():
    task = {"target_agent": "linux-worker", "artifacts": [1]}
    result = {"artifacts": [{"path": "other.txt", "sha256": HELLO}]}
    assert verify_artifacts(task, result, local_verify=_local_ok) == "FAIL"


def test_dict_task_hash_mismatch_fails_and_match_can_pass(monkeypatch):
    monkeypatch.setattr(
        "scripts.courier_verifier.verify_uploaded_artifact",
        lambda *_args, **_kwargs: (True, "ok"),
    )

    def fetch(_artifact_id):
        return {"id": "art"}, b"hello"

    task = {
        "target_agent": "mac-worker",
        "artifacts": [{"path": "remote.txt", "expected_sha256": "f" * 64}],
    }
    result = {"artifacts": [{"path": "remote.txt", "artifact_id": "art-1", "expected_sha256": HELLO}]}
    assert verify_artifacts(task, result, fetch=fetch) == "FAIL"

    task["artifacts"][0]["expected_sha256"] = HELLO
    assert verify_artifacts(task, result, fetch=fetch) == "PASS"
    again = verify_artifacts(task, result, fetch=fetch)
    assert again == "PASS"


def test_parallel_verifier_tests_both_remain():
    """Same test names on the live verifier and the head snapshot are not duplicates to delete."""
    import tests.test_courier_verifier as live
    import tests.test_courier_verifier_head_prev as snapshot

    assert live.verify_artifacts is not snapshot.verify_artifacts
    assert callable(live.test_verify_artifact_missing)
    assert callable(snapshot.test_verify_artifact_missing)
    assert callable(live.test_verify_artifacts_no_artifacts)
    assert callable(snapshot.test_verify_artifacts_no_artifacts)


def test_string_list_omission_still_fails():
    task = {"artifacts": ["output.txt"], "target_agent": "linux-worker"}
    result = {"artifacts": [{"path": "other.txt", "sha256": HELLO}]}
    assert verify_artifacts(task, result, local_verify=_local_ok) == "FAIL"
