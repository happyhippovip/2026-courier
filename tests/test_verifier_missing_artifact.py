"""L4 pin: Ensure verification fails closed if an artifact claimed in receipt does not physically exist.

Covers both:
1. Direct adapter verification (adapters.synthetic.verify)
2. Controller verifier hand-off (courier_core.verification.run_verifier)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import adapter_verifier, run_verifier


def make_task(**overrides) -> TaskState:
    defaults = dict(
        task_id="t-art-missing",
        status=TaskStatus.VERIFYING,
        adapter="synthetic",
        params={"write": "out.txt", "content": "hello world"},
        effect_class="idempotent",
        max_attempts=3,
        lease_ttl_s=60,
        timeout_s=None,
        dispatch_id="disp-001",
    )
    defaults.update(overrides)
    return TaskState(**defaults)


def make_result(artifacts, **overrides) -> Event:
    payload = {
        "outcome": "success",
        "artifacts": artifacts,
    }
    defaults = dict(
        type=EventType.RESULT_READY,
        task_id="t-art-missing",
        attempt=1,
        dispatch_id="disp-001",
        worker_id="w-001",
        result_id="res-001",
        payload=payload,
    )
    defaults.update(overrides)
    return Event(**defaults)


def test_missing_artifact_file_is_rejected_fail_closed(tmp_path: Path):
    """When an artifact is listed with a valid hash but does not exist on disk, verdict must reject."""
    claimed_sha = hashlib.sha256(b"hello world").hexdigest()
    result = make_result([{"path": "out.txt", "sha256": claimed_sha}])
    task = make_task()

    # The file does not exist in tmp_path
    assert not (tmp_path / "out.txt").exists()

    verdict = run_verifier(adapter_verifier, task, result, tmp_path)
    assert verdict.accepted is False
    assert "evidence file missing" in verdict.reason
    assert verdict.verifier is not None


def test_unreadable_missing_dispatch_artifact_is_rejected(tmp_path: Path):
    """When dispatch-namespaced artifact directory does not contain the file, verdict rejects."""
    claimed_sha = hashlib.sha256(b"hello world").hexdigest()
    result = make_result([{"path": "artifacts/disp-001/out.txt", "sha256": claimed_sha}])
    task = make_task()

    assert not (tmp_path / "artifacts" / "disp-001" / "out.txt").exists()

    verdict = run_verifier(adapter_verifier, task, result, tmp_path)
    assert verdict.accepted is False
    assert "evidence file missing" in verdict.reason


def test_present_artifact_with_tampered_bytes_is_rejected(tmp_path: Path):
    """When an artifact exists but content bytes differ from claimed hash, verdict rejects."""
    claimed_sha = hashlib.sha256(b"hello world").hexdigest()
    (tmp_path / "out.txt").write_bytes(b"tampered bytes")

    result = make_result([{"path": "out.txt", "sha256": claimed_sha}])
    task = make_task()

    verdict = run_verifier(adapter_verifier, task, result, tmp_path)
    assert verdict.accepted is False
    assert "evidence artifact hash does not match" in verdict.reason


def test_present_valid_artifact_is_accepted(tmp_path: Path):
    """When the artifact exists and matches claimed hash and synthetic content, verdict accepts."""
    content = b"hello world"
    claimed_sha = hashlib.sha256(content).hexdigest()
    (tmp_path / "out.txt").write_bytes(content)

    result = make_result([{"path": "out.txt", "sha256": claimed_sha}])
    task = make_task()

    verdict = run_verifier(adapter_verifier, task, result, tmp_path)
    assert verdict.accepted is True
    assert "synthetic evidence verified" in verdict.reason


def test_symlink_path_escape_is_rejected_fail_closed(tmp_path: Path):
    """When an artifact inside workspace is a symlink pointing outside scope, verdict must reject."""
    outside_dir = tmp_path.parent / "outside_scope"
    outside_dir.mkdir(parents=True, exist_ok=True)
    secret_file = outside_dir / "secret.txt"
    content = b"secret content"
    secret_file.write_bytes(content)
    claimed_sha = hashlib.sha256(content).hexdigest()

    symlink_path = tmp_path / "link_escape.txt"
    try:
        symlink_path.symlink_to(secret_file)
    except OSError:
        pytest.skip("Symlinks not supported on this platform/configuration")

    result = make_result([{"path": "link_escape.txt", "sha256": claimed_sha}])
    task = make_task(params={"write": "link_escape.txt", "content": "secret content"})

    verdict = run_verifier(adapter_verifier, task, result, tmp_path)
    assert verdict.accepted is False
    assert "evidence artifact path escapes the work scope" in verdict.reason


def test_false_success_with_empty_evidence_is_rejected_fail_closed(tmp_path: Path):
    """When worker reports success outcome but artifact list is empty, verdict must reject fail-closed."""
    result = make_result([])  # outcome="success", artifacts=[]
    task = make_task()

    verdict = run_verifier(adapter_verifier, task, result, tmp_path)
    assert verdict.accepted is False
    assert "missing evidence" in verdict.reason


def test_foreign_dispatch_evidence_is_rejected_fail_closed(tmp_path: Path):
    """When evidence is bound to a different dispatch, verdict must reject fail-closed."""
    content = b"hello world"
    claimed_sha = hashlib.sha256(content).hexdigest()
    (tmp_path / "out.txt").write_bytes(content)

    # Result bound to disp-foreign instead of disp-001
    result = make_result([{"path": "out.txt", "sha256": claimed_sha}], dispatch_id="disp-foreign")
    task = make_task(dispatch_id="disp-001")

    verdict = run_verifier(adapter_verifier, task, result, tmp_path)
    assert verdict.accepted is False
    assert "evidence is bound to a different dispatch" in verdict.reason

