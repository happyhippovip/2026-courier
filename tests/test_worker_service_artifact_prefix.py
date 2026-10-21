"""P9 test hardening for courier_worker.service pure helpers (offline).

Covers ``_artifact_prefix``, ``build_spec_failure_payload``, the
``CANCEL_TYPES`` contract, and ``CancelWatcher._dispatch_event`` — all pure
and offline. No network, no credentials, no subprocesses.
"""

import json
import os

from courier_worker import service as S


def _watcher(task_id="task-1"):
    return S.CancelWatcher("http://127.0.0.1:9", "token", task_id)


# -- _artifact_prefix -------------------------------------------------------

def test_artifact_prefix_inside_home(tmp_path):
    home = tmp_path / "home"
    artifact = home / "artifacts" / "d123"
    home.mkdir()
    artifact.mkdir(parents=True)
    assert S._artifact_prefix(str(artifact), str(home)) == "artifacts/d123/"


def test_artifact_prefix_nested_depth(tmp_path):
    home = tmp_path / "h"
    artifact = home / "a" / "b" / "c"
    artifact.mkdir(parents=True)
    assert S._artifact_prefix(str(artifact), str(home)) == "a/b/c/"


def test_artifact_prefix_none_home(tmp_path):
    artifact = tmp_path / "artifacts" / "d1"
    artifact.mkdir(parents=True)
    assert S._artifact_prefix(str(artifact), None) == ""


def test_artifact_prefix_empty_home(tmp_path):
    artifact = tmp_path / "artifacts" / "d1"
    artifact.mkdir(parents=True)
    assert S._artifact_prefix(str(artifact), "") == ""


def test_artifact_prefix_same_dir_is_empty(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert S._artifact_prefix(str(home), str(home)) == ""


def test_artifact_prefix_outside_home_is_empty(tmp_path):
    home = tmp_path / "home"
    outside = tmp_path / "other" / "d1"
    home.mkdir()
    outside.mkdir(parents=True)
    assert S._artifact_prefix(str(outside), str(home)) == ""


def test_artifact_prefix_parent_of_home_is_empty(tmp_path):
    home = tmp_path / "home" / "sub"
    home.mkdir(parents=True)
    assert S._artifact_prefix(str(tmp_path), str(home)) == ""


def test_artifact_prefix_uses_forward_slashes(tmp_path):
    home = tmp_path / "home"
    artifact = home / "artifacts" / "d1"
    artifact.mkdir(parents=True)
    prefix = S._artifact_prefix(str(artifact), str(home))
    assert "\\" not in prefix
    assert prefix.endswith("/")


def test_artifact_prefix_trailing_slash_inputs(tmp_path):
    home = tmp_path / "home"
    artifact = home / "artifacts" / "d9"
    artifact.mkdir(parents=True)
    assert S._artifact_prefix(str(artifact) + os.sep, str(home) + os.sep) == "artifacts/d9/"


# -- build_spec_failure_payload ----------------------------------------------

def test_spec_failure_payload_shape():
    payload = S.build_spec_failure_payload("dispatch-1", "r-dispatch-1", "spec-invalid: bad")
    assert payload == {
        "dispatch_id": "dispatch-1",
        "result_id": "r-dispatch-1",
        "artifacts": [],
        "outcome": "failure",
        "retryable": False,
        "reason": "spec-invalid: bad",
    }


def test_spec_failure_payload_never_retryable():
    payload = S.build_spec_failure_payload("d", "r-d", "x")
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert payload["artifacts"] == []


def test_spec_failure_payload_preserves_ids_verbatim():
    payload = S.build_spec_failure_payload("D-1", "R-1", "why")
    assert payload["dispatch_id"] == "D-1"
    assert payload["result_id"] == "R-1"
    assert payload["reason"] == "why"


# -- CANCEL_TYPES --------------------------------------------------------------

def test_cancel_types_contract():
    assert S.CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
    assert isinstance(S.CANCEL_TYPES, frozenset)


# -- CancelWatcher._dispatch_event (pure, no sockets) ---------------------------

def test_dispatch_cancel_requested_sets_cancelled():
    watcher = _watcher("task-1")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "task-1"})])
    assert watcher.cancelled() is True


def test_dispatch_cancelled_sets_cancelled():
    watcher = _watcher("task-7")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED", "task_id": "task-7"})])
    assert watcher.cancelled() is True


def test_dispatch_non_cancel_ignored():
    watcher = _watcher("task-1")
    watcher._dispatch_event([json.dumps({"type": "TASK_STARTED", "task_id": "task-1"})])
    assert watcher.cancelled() is False


def test_dispatch_wrong_task_ignored():
    watcher = _watcher("task-1")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED", "task_id": "other"})])
    assert watcher.cancelled() is False


def test_dispatch_malformed_json_ignored():
    watcher = _watcher("task-1")
    watcher._dispatch_event(["{not json"])
    assert watcher.cancelled() is False


def test_dispatch_non_dict_json_ignored():
    watcher = _watcher("task-1")
    watcher._dispatch_event([json.dumps(["TASK_CANCELLED"])])
    assert watcher.cancelled() is False


def test_dispatch_empty_lines_ignored():
    watcher = _watcher("task-1")
    watcher._dispatch_event([])
    assert watcher.cancelled() is False


def test_dispatch_nested_payload_form():
    watcher = _watcher("task-3")
    body = json.dumps({"payload": {"type": "TASK_CANCEL_REQUESTED", "task_id": "task-3"}})
    watcher._dispatch_event([body])
    assert watcher.cancelled() is True


def test_dispatch_event_type_alias():
    watcher = _watcher("task-4")
    watcher._dispatch_event([json.dumps({"event_type": "TASK_CANCELLED", "task_id": "task-4"})])
    assert watcher.cancelled() is True


def test_dispatch_missing_task_id_ignored():
    watcher = _watcher("task-1")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED"})])
    assert watcher.cancelled() is False
