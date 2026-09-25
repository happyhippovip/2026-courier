"""Default result_id binding for work_queue.cmd_complete (Result Binding).

Tasks completed without an explicit result_id and without dispatch
identity (attempt_id/dispatch_id) must not share one static
"<task_id>:r1" identity: distinct completions get distinct ids, while an
identical retry stays idempotent (same id marks the duplicate).
"""
import hashlib
import json
import types

from scripts import work_queue


def _complete(task_extra, result_json, stage="ACCEPTED"):
    task = {"task_id": "T1", "status": "CLAIMED", **task_extra}
    data = {"packages": {}, "tasks": {"T1": task}, "leases": {"T1": {}}}
    args = types.SimpleNamespace(
        task_id="T1", result_json=json.dumps(result_json), stage=stage)
    out = work_queue.cmd_complete(args, data, 0.0)
    assert out.get("done") == "T1", out
    return data["tasks"]["T1"]["result_id"]


def test_default_id_is_content_bound_not_static():
    rid = _complete({}, {"output": "alpha"})
    assert rid.startswith("result-")
    assert rid != "T1:r1"


def test_distinct_contents_yield_distinct_ids():
    assert _complete({}, {"output": "alpha"}) != _complete({}, {"output": "beta"})


def test_identical_retry_yields_same_id():
    assert _complete({}, {"output": "alpha"}) == _complete({}, {"output": "alpha"})


def test_dispatch_identity_path_pinned_and_stable():
    extra = {"attempt_id": "a1", "dispatch_id": "d1", "executor_kind": "LOCAL_FAKE"}
    expected = "result-" + hashlib.sha256(json.dumps(
        {"task_id": "T1", "attempt_id": "a1", "dispatch_id": "d1",
         "executor_kind": "LOCAL_FAKE"},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert _complete(extra, {"output": "alpha"}) == expected
    assert _complete(extra, {"output": "alpha"}) == _complete(extra, {"output": "beta"})


def test_explicit_result_id_preserved():
    assert _complete({}, {"result_id": "custom-1"}) == "custom-1"
