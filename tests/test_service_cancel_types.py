"""P9 hardening for courier_worker.service CANCEL_TYPES + dispatch (tests only).

Pins the offline cancel-matching contract without any network:
- CANCEL_TYPES holds exactly the two documented cancel event names.
- CancelWatcher._dispatch_event sets cancelled only for a cancel type whose
  task id matches, and ignores everything else (fail-closed, no raise).
"""

from __future__ import annotations

import json

from courier_worker import service as S


def _watcher(task_id="t-1"):
    return S.CancelWatcher("http://127.0.0.1:9", "test-token", task_id, timeout_s=5.0)


def test_cancel_types_exact_and_frozen():
    assert S.CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
    assert isinstance(S.CANCEL_TYPES, frozenset)


def test_watcher_starts_uncancelled():
    w = _watcher("t-1")
    assert w.cancelled() is False
    assert w.degraded is False


def test_dispatch_requested_matching_sets_cancelled():
    w = _watcher("t-1")
    w._dispatch_event([json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "t-1"})])
    assert w.cancelled() is True


def test_dispatch_cancelled_matching_sets_cancelled():
    w = _watcher("t-1")
    w._dispatch_event([json.dumps({"type": "TASK_CANCELLED", "task_id": "t-1"})])
    assert w.cancelled() is True


def test_dispatch_mismatched_task_id_ignored():
    w = _watcher("t-1")
    w._dispatch_event([json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "t-other"})])
    assert w.cancelled() is False


def test_dispatch_non_cancel_type_ignored():
    w = _watcher("t-1")
    w._dispatch_event([json.dumps({"type": "TASK_COMPLETED", "task_id": "t-1"})])
    assert w.cancelled() is False


def test_dispatch_empty_and_malformed_ignored():
    w = _watcher("t-1")
    w._dispatch_event([])
    assert w.cancelled() is False
    w._dispatch_event(["not-json{{"])
    assert w.cancelled() is False
    w._dispatch_event([json.dumps(["a", "list"])])
    assert w.cancelled() is False
    w._dispatch_event([json.dumps({"type": "TASK_CANCELLED"})])
    assert w.cancelled() is False


def test_dispatch_payload_wrapped_cancel_matching():
    w = _watcher("t-7")
    body = json.dumps({"payload": {"type": "TASK_CANCEL_REQUESTED", "task_id": "t-7"}})
    w._dispatch_event([body])
    assert w.cancelled() is True


def test_dispatch_event_type_alias_matching():
    w = _watcher("t-9")
    w._dispatch_event([json.dumps({"event_type": "TASK_CANCELLED", "task_id": "t-9"})])
    assert w.cancelled() is True
