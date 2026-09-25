"""Regression: canonical result_id binding for motor + work queue (priority 3).

Pins the Duplicate-Execution/Result-Identity fix: default result
identities are a stable hash over (task_id, attempt_id, dispatch_id,
executor_kind) — never the volatile "<task_id>:r1" form — so
Crash/Resume and retries cannot silently reuse or collide on a stale
binding.
"""
import hashlib
import json
from argparse import Namespace

from scripts.cannon_motor import deterministic_executor
from scripts.work_queue import cmd_complete


def make_task(**overrides):
    base = {"task_id": "t1", "attempt_id": "a1", "dispatch_id": "d1"}
    base.update(overrides)
    return base


def canonical(task_id, attempt_id, dispatch_id, executor_kind="LOCAL_FAKE"):
    payload = json.dumps(
        {"task_id": task_id, "attempt_id": attempt_id,
         "dispatch_id": dispatch_id, "executor_kind": executor_kind},
        sort_keys=True, separators=(",", ":")).encode()
    return "result-" + hashlib.sha256(payload).hexdigest()


def test_same_identity_same_result_id(tmp_path):
    _, first = deterministic_executor(tmp_path, make_task())
    _, second = deterministic_executor(tmp_path, make_task())
    assert first == second == canonical("t1", "a1", "d1")


def test_retry_identity_changes_result_id(tmp_path):
    _, base = deterministic_executor(tmp_path, make_task())
    _, retry = deterministic_executor(
        tmp_path, make_task(attempt_id="a2", dispatch_id="d2"))
    assert retry != base
    assert retry == canonical("t1", "a2", "d2")


def test_never_volatile_result_id_form(tmp_path):
    _, rid = deterministic_executor(tmp_path, make_task())
    assert rid != "t1:r1"
    assert rid.startswith("result-")


def test_work_queue_complete_default_binds_identity():
    data = {"tasks": {"t1": dict(make_task(), status="CLAIMED")},
            "leases": {"t1": {}}}
    args = Namespace(task_id="t1", result_json="{}", stage="EVIDENCE_READY")
    out = cmd_complete(args, data, 0.0)
    assert out["done"] == "t1"
    assert data["tasks"]["t1"]["result_id"] == canonical("t1", "a1", "d1")


def test_work_queue_legacy_default_never_volatile():
    data = {"tasks": {"t1": {"task_id": "t1", "status": "CLAIMED"}},
            "leases": {"t1": {}}}
    args = Namespace(task_id="t1", result_json="{}", stage="EVIDENCE_READY")
    cmd_complete(args, data, 0.0)
    assert data["tasks"]["t1"]["result_id"] == canonical(
        "t1", None, None, "LOCAL_FAKE")
    assert data["tasks"]["t1"]["result_id"] != "t1:r1"


def test_yolo_canonical_binding_retry_distinct():
    assert canonical("t1", "a1", "d1", "YOLO") != canonical(
        "t1", "a2", "d2", "YOLO")
    assert canonical("t1", "a1", "d1", "YOLO").startswith("result-")


def test_work_queue_complete_explicit_result_id_preserved():
    data = {"tasks": {"t1": dict(make_task(), status="CLAIMED")},
            "leases": {"t1": {}}}
    args = Namespace(
        task_id="t1",
        result_json=json.dumps({"result_id": "result-explicit"}),
        stage="ACCEPTED")
    cmd_complete(args, data, 0.0)
    assert data["tasks"]["t1"]["result_id"] == "result-explicit"
    assert data["tasks"]["t1"]["status"] == "DONE"
