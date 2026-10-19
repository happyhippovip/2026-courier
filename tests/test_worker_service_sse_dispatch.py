"""P9 pins for courier_worker.service CancelWatcher._dispatch_event.

The SSE dispatch step is pure and offline: it folds one event's data lines
into the watcher's cancelled flag. No sockets, no threads, no network.
"""

import json

from courier_worker.service import CANCEL_TYPES, CancelWatcher


def _watcher(task_id="t-1"):
    # The base URL is never contacted by _dispatch_event; it only needs to
    # look like a URL so constructor validation (if any) stays quiet.
    return CancelWatcher("http://controller.invalid", "test-token", task_id)


def test_empty_data_lines_never_cancel():
    watcher = _watcher()
    watcher._dispatch_event([])
    assert not watcher.cancelled()


def test_invalid_json_is_ignored():
    watcher = _watcher()
    watcher._dispatch_event(["this is not json {"])
    assert not watcher.cancelled()


def test_non_dict_json_is_ignored():
    watcher = _watcher()
    watcher._dispatch_event([json.dumps(["TASK_CANCELLED", "t-1"])])
    assert not watcher.cancelled()


def test_cancel_requested_matching_task_sets_cancelled():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "t-9"})])
    assert watcher.cancelled()


def test_cancelled_matching_task_sets_cancelled():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED", "task_id": "t-9"})])
    assert watcher.cancelled()


def test_cancel_for_other_task_is_ignored():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED", "task_id": "t-other"})])
    assert not watcher.cancelled()


def test_non_cancel_type_is_ignored():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"type": "TASK_STARTED", "task_id": "t-9"})])
    assert not watcher.cancelled()


def test_type_nested_in_payload_dict_still_cancels():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"payload": {"type": "TASK_CANCELLED"}, "task_id": "t-9"})])
    assert watcher.cancelled()


def test_task_id_nested_in_payload_dict_still_cancels():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED", "payload": {"task_id": "t-9"}})])
    assert watcher.cancelled()


def test_event_type_key_variant_is_honoured():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"event_type": "TASK_CANCEL_REQUESTED", "task_id": "t-9"})])
    assert watcher.cancelled()


def test_missing_type_keys_never_cancel():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"task_id": "t-9"})])
    assert not watcher.cancelled()


def test_cancel_without_task_id_never_cancels():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCELLED"})])
    assert not watcher.cancelled()


def test_non_dict_payload_falls_back_to_top_level_keys():
    watcher = _watcher("t-9")
    watcher._dispatch_event([json.dumps(
        {"type": "TASK_CANCELLED", "task_id": "t-9", "payload": "not-a-dict"})])
    assert watcher.cancelled()


def test_multiple_data_lines_are_joined_as_one_document():
    watcher = _watcher("t-9")
    watcher._dispatch_event(['{"type":', '"TASK_CANCELLED", "task_id": "t-9"}'])
    assert watcher.cancelled()


def test_cancel_types_cover_both_documented_events():
    assert CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
