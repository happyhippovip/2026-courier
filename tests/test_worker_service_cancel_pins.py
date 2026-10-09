"""P9 hardening pins for courier_worker.service pure helpers (offline only).

Covers, without any network:
- ControllerClient URL validation (fail-closed, no connection made)
- _artifact_prefix (pure path scoping)
- build_spec_failure_payload (fixed failure shape)
- CancelWatcher._dispatch_event (pure SSE data-line parsing)
"""

import json

import pytest

from courier_worker.service import (
    CANCEL_TYPES,
    ControllerClient,
    ControllerError,
    CancelWatcher,
    _artifact_prefix,
    build_spec_failure_payload,
)


def _watcher(task_id="task-1"):
    return CancelWatcher("http://controller.invalid", "dummy", task_id)


# -- ControllerClient URL validation (no network) ---------------------------


def test_client_accepts_http_and_strips_slash():
    client = ControllerClient("http://controller.invalid/", "dummy")
    assert client.base_url == "http://controller.invalid"
    assert client.token == "dummy"


def test_client_accepts_https_with_port():
    client = ControllerClient("https://controller.invalid:8443/v1", "dummy", timeout_s=2.5)
    assert client.timeout_s == 2.5


def test_client_rejects_bare_name():
    with pytest.raises(ControllerError):
        ControllerClient("controller", "dummy")


def test_client_rejects_wrong_scheme():
    with pytest.raises(ControllerError):
        ControllerClient("ftp://controller.invalid/", "dummy")


def test_client_rejects_empty():
    with pytest.raises(ControllerError):
        ControllerClient("", "dummy")


def test_client_rejects_missing_hostname():
    with pytest.raises(ControllerError):
        ControllerClient("http://", "dummy")


# -- _artifact_prefix --------------------------------------------------------


def test_artifact_prefix_empty_without_home(tmp_path):
    assert _artifact_prefix(str(tmp_path / "artifacts" / "d1"), None) == ""
    assert _artifact_prefix(str(tmp_path / "artifacts" / "d1"), "") == ""


def test_artifact_prefix_inside_home(tmp_path):
    home = str(tmp_path)
    artifact_dir = str(tmp_path / "artifacts" / "d1")
    assert _artifact_prefix(artifact_dir, home) == "artifacts/d1/"


def test_artifact_prefix_outside_home_is_empty(tmp_path):
    home = str(tmp_path / "home")
    artifact_dir = str(tmp_path / "other" / "d1")
    assert _artifact_prefix(artifact_dir, home) == ""


def test_artifact_prefix_equal_to_home_is_empty(tmp_path):
    home = str(tmp_path)
    assert _artifact_prefix(home, home) == ""


# -- build_spec_failure_payload ----------------------------------------------


def test_spec_failure_payload_shape():
    payload = build_spec_failure_payload("dispatch-1", "r-dispatch-1", "no task_id")
    assert payload == {
        "dispatch_id": "dispatch-1",
        "result_id": "r-dispatch-1",
        "artifacts": [],
        "outcome": "failure",
        "retryable": False,
        "reason": "no task_id",
    }


# -- CancelWatcher._dispatch_event (pure, no socket) --------------------------


def test_dispatch_event_empty_is_noop():
    watcher = _watcher()
    watcher._dispatch_event([])
    assert not watcher.cancelled()


def test_dispatch_event_bad_json_is_noop():
    watcher = _watcher()
    watcher._dispatch_event(["not-json{"])
    assert not watcher.cancelled()


def test_dispatch_event_non_dict_is_noop():
    watcher = _watcher()
    watcher._dispatch_event([json.dumps(["TASK_CANCELLED"])])
    assert not watcher.cancelled()


def test_dispatch_event_cancel_requested_matching_task():
    watcher = _watcher("task-1")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "task-1"})])
    assert watcher.cancelled()


def test_dispatch_event_cancelled_matching_task():
    watcher = _watcher("task-7")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED", "task_id": "task-7"})])
    assert watcher.cancelled()


def test_dispatch_event_other_type_does_not_cancel():
    watcher = _watcher("task-1")
    watcher._dispatch_event([json.dumps({"type": "TASK_PROGRESS", "task_id": "task-1"})])
    assert not watcher.cancelled()


def test_dispatch_event_wrong_task_does_not_cancel():
    watcher = _watcher("task-1")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED", "task_id": "task-2"})])
    assert not watcher.cancelled()


def test_dispatch_event_nested_payload_form():
    watcher = _watcher("task-9")
    watcher._dispatch_event(
        [json.dumps({"payload": {"type": "TASK_CANCEL_REQUESTED", "task_id": "task-9"}})]
    )
    assert watcher.cancelled()


def test_dispatch_event_event_type_key_variant():
    watcher = _watcher("task-3")
    watcher._dispatch_event([json.dumps({"event_type": "TASK_CANCELLED", "task_id": "task-3"})])
    assert watcher.cancelled()


def test_cancel_types_cover_both_cancel_states():
    assert CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
