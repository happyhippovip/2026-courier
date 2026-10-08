"""Controller verifier for provider_exec. Imports adapters.provider_exec directly.

The runner that must save Muse output as provider_output.txt is
courier_worker/adapter_runner.py, owned by open PRs #141 and #165. These tests
do not edit that file. They build the evidence the verifier reads.
"""

import hashlib
import os
from pathlib import Path

from adapters import provider_exec
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskStatus, TaskState
from courier_core.verification import adapter_verifier, run_verifier

DISPATCH = "d1"
EVIDENCE = f"artifacts/{DISPATCH}/provider_output.txt"
OUTPUT = "out.txt"
MAX_BYTES = 1024 * 1024


def task(**changes):
    value = dict(
        task_id="t1", status=TaskStatus.VERIFYING, adapter="provider_exec",
        params={
            "provider": "muse",
            "prompt": "summarize the unit",
            "workspace": "workspace",
            "expected_outputs": [{"path": OUTPUT, "content": "unit-ok"}],
        },
        effect_class="non_idempotent", max_attempts=1, lease_ttl_s=60,
        timeout_s=None, dispatch_id=DISPATCH,
    )
    value.update(changes)
    return TaskState(**value)


def ready(payload, dispatch_id=DISPATCH):
    return Event(
        type=EventType.RESULT_READY, task_id="t1", attempt=1,
        dispatch_id=dispatch_id, worker_id="w1", result_id="r1", payload=payload,
    )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _put(home: Path, rel: str, data: bytes) -> dict:
    path = home / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": rel, "sha256": _sha(data)}


def _success(home: Path, evidence: bytes = b"provider-ok\n", pinned: bytes = b"unit-ok",
             **payload):
    artifacts = [
        _put(home, EVIDENCE, evidence),
        _put(home, f"workspace/{OUTPUT}", pinned),
    ]
    body = {"outcome": "success", "artifacts": artifacts, "exit_code": 0}
    body.update(payload)
    return body


def snapshot(root: Path):
    found = {}
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            path = Path(dirpath) / name
            rel = str(path.relative_to(root))
            if path.is_symlink():
                found[rel] = ("symlink", os.readlink(path))
            else:
                found[rel] = ("file", _sha(path.read_bytes()))
    return found


def test_max_evidence_is_one_mib():
    assert provider_exec.MAX_EVIDENCE_BYTES == MAX_BYTES


def test_accepts_pinned_output_and_bounded_evidence(tmp_path):
    home = tmp_path / "home"
    payload = _success(home)
    spec = task()
    verdict = provider_exec.verify(spec, ready(payload), home)
    assert verdict.accepted is True
    assert verdict.retryable is False
    assert verdict.verifier is None
    assert adapter_verifier("provider_exec") is provider_exec.verify
    stamped = run_verifier(adapter_verifier, spec, ready(payload), home)
    assert stamped.accepted is True
    assert stamped.verifier["name"].startswith("adapters.provider_exec.")
    foreign = provider_exec.verify(spec, ready(payload, dispatch_id="other"), home)
    assert foreign.accepted is False


def test_rejects_wrong_content(tmp_path):
    home = tmp_path / "home"
    payload = _success(home, pinned=b"not-the-pin")
    verdict = provider_exec.verify(task(), ready(payload), home)
    assert verdict.accepted is False
    assert "does not match" in verdict.reason

    home_sha = tmp_path / "sha"
    payload_sha = _success(home_sha)
    params = task().params
    params["expected_outputs"] = [{"path": OUTPUT, "sha256": _sha(b"unit-ok-other")}]
    verdict_sha = provider_exec.verify(task(params=params), ready(payload_sha), home_sha)
    assert verdict_sha.accepted is False
    assert "does not match" in verdict_sha.reason


def test_rejects_missing_file(tmp_path):
    home = tmp_path / "home"
    pinned = _put(home, f"workspace/{OUTPUT}", b"unit-ok")
    missing_evidence = {
        "outcome": "success",
        "exit_code": 0,
        "artifacts": [{"path": EVIDENCE, "sha256": _sha(b"absent")}, pinned],
    }
    verdict = provider_exec.verify(task(), ready(missing_evidence), home)
    assert verdict.accepted is False
    assert "missing" in verdict.reason

    home_out = tmp_path / "no-pin"
    evidence = _put(home_out, EVIDENCE, b"provider-ok\n")
    absent_pin = {"outcome": "success", "exit_code": 0, "artifacts": [evidence]}
    verdict_pin = provider_exec.verify(task(), ready(absent_pin), home_out)
    assert verdict_pin.accepted is False
    assert "missing" in verdict_pin.reason


def test_rejects_traversal_and_symlink_escape(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"secret")
    digest = _sha(b"secret")
    home = tmp_path / "home"
    pinned = _put(home, f"workspace/{OUTPUT}", b"unit-ok")
    traversed = {
        "outcome": "success",
        "exit_code": 0,
        "artifacts": [{"path": "../secret.txt", "sha256": digest}, pinned],
    }
    verdict = provider_exec.verify(task(), ready(traversed), home)
    assert verdict.accepted is False
    assert "escapes" in verdict.reason
    assert secret.read_bytes() == b"secret"

    linked = tmp_path / "linked"
    outside = tmp_path / "outside-output.txt"
    outside.write_bytes(b"outside-muse")
    evidence = linked / EVIDENCE
    evidence.parent.mkdir(parents=True)
    os.symlink(outside, evidence)
    _put(linked, f"workspace/{OUTPUT}", b"unit-ok")
    payload = {
        "outcome": "success",
        "exit_code": 0,
        "artifacts": [
            {"path": EVIDENCE, "sha256": _sha(b"outside-muse")},
            {"path": f"workspace/{OUTPUT}", "sha256": _sha(b"unit-ok")},
        ],
    }
    before = outside.read_bytes()
    escaped = provider_exec.verify(task(), ready(payload), linked)
    assert escaped.accepted is False
    assert "escapes" in escaped.reason
    assert outside.read_bytes() == before


def test_rejects_oversize(tmp_path):
    home = tmp_path / "home"
    payload = _success(home, evidence=b"x" * (MAX_BYTES + 1))
    verdict = provider_exec.verify(task(), ready(payload), home)
    assert verdict.accepted is False
    assert "1 MiB" in verdict.reason

    bounded = tmp_path / "bounded"
    ok = _success(bounded, evidence=b"y" * MAX_BYTES)
    accepted = provider_exec.verify(task(), ready(ok), bounded)
    assert accepted.accepted is True


def test_rejects_nonzero_exit(tmp_path):
    home = tmp_path / "home"
    payload = _success(home, exit_code=1)
    verdict = provider_exec.verify(task(), ready(payload), home)
    assert verdict.accepted is False
    assert "non-zero" in verdict.reason
    stamped = run_verifier(adapter_verifier, task(), ready(payload), home)
    assert stamped.accepted is False

    failed = tmp_path / "failed"
    failure = _success(failed)
    failure["outcome"] = "failure"
    failure["exit_code"] = 3
    failure["reason"] = "NONZERO_EXIT exit=3"
    failure["retryable"] = False
    rejected = provider_exec.verify(task(), ready(failure), failed)
    assert rejected.accepted is False


def test_replay_is_read_only(tmp_path):
    home = tmp_path / "home"
    payload = _success(home)
    spec = task()
    event = ready(payload)
    before = snapshot(home)
    first = provider_exec.verify(spec, event, home)
    second = provider_exec.verify(spec, event, home)
    assert first.accepted is True and second.accepted is True
    assert first.reason == second.reason
    assert snapshot(home) == before
