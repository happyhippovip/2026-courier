import json
import os
import stat as statmod
import threading

import pytest

from courier_overlay import (
    EVENT_TYPES,
    EventBusError,
    emit,
    read_events,
    replay,
    scan_report,
)


def _bus(tmp_path):
    return str(tmp_path / "events.jsonl")


def test_emit_roundtrip_all_lifecycle_types(tmp_path):
    bus = _bus(tmp_path)
    for i, event_type in enumerate(sorted(EVENT_TYPES)):
        record = emit(bus, "agent-1", f"task-{i}", event_type, f"summary {i}")
        assert record["event_type"] == event_type
        assert record["timestamp"].endswith("+00:00")
    assert len(read_events(bus)) == len(EVENT_TYPES)


def test_emit_rejects_unknown_event_type(tmp_path):
    with pytest.raises(EventBusError):
        emit(_bus(tmp_path), "a", "t", "NOPE_NOT_A_TYPE", "x")


def test_emit_rejects_empty_ids_and_summary(tmp_path):
    bus = _bus(tmp_path)
    for agent_id, task_id, summary in [("", "t", "s"), ("a", "", "s"), ("a", "t", "  ")]:
        with pytest.raises(EventBusError):
            emit(bus, agent_id, task_id, "TASK_BLOCKED", summary)
    assert not os.path.exists(bus)


def test_emit_rejects_secret_shaped_summary(tmp_path):
    bus = _bus(tmp_path)
    for bad in (
        "api_key=AKIA1234567890",
        "Authorization: Bearer secret-token-value",
        "-----BEGIN PRIVATE KEY-----",
        "password: hunter2",
    ):
        with pytest.raises(EventBusError, match="[Ss]ecret"):
            emit(bus, "a", "t", "WORKER_PROGRESS", f"progress note {bad}")
    assert not os.path.exists(bus)


def test_emit_rejects_oversize_summary(tmp_path):
    with pytest.raises(EventBusError, match="exceeds"):
        emit(_bus(tmp_path), "a", "t", "WORKER_PROGRESS", "x" * 241)


def test_read_filters_and_replay_order(tmp_path):
    bus = _bus(tmp_path)
    emit(bus, "a1", "t1", "WORKER_STARTED", "s1")
    emit(bus, "a1", "t2", "RESULT_READY", "s2")
    emit(bus, "a2", "t1", "TASK_COMPLETE", "s3")
    assert [e["event_type"] for e in replay(bus)] == [
        "WORKER_STARTED", "RESULT_READY", "TASK_COMPLETE",
    ]
    assert len(read_events(bus, task_id="t1")) == 2
    assert len(read_events(bus, event_type="RESULT_READY")) == 1
    assert len(read_events(bus, agent_id="a2")) == 1
    assert read_events(bus, task_id="missing") == []


def test_read_missing_file_returns_empty(tmp_path):
    assert read_events(_bus(tmp_path)) == []


def test_read_skips_corrupt_lines(tmp_path):
    bus = _bus(tmp_path)
    emit(bus, "a", "t", "TASK_BLOCKED", "good")
    with open(bus, "ab") as f:
        f.write(b"not-json{\n")
    assert len(read_events(bus)) == 1


def test_replay_is_idempotent_for_observers(tmp_path):
    """Replaying the same file twice yields the same sequence, so a
    last-writer-wins observer fold converges (dup-tolerance contract)."""
    bus = _bus(tmp_path)
    emit(bus, "a1", "t1", "WORKER_STARTED", "s1")
    emit(bus, "a1", "t1", "WORKER_PROGRESS", "s2")
    emit(bus, "a1", "t1", "TASK_COMPLETE", "s3")
    first = list(replay(bus))
    second = list(replay(bus))
    assert first == second

    def fold(events):
        state = {}
        for e in events:
            state[e["task_id"]] = e["event_type"]
        return state

    assert fold(first) == fold(second) == {"t1": "TASK_COMPLETE"}


def test_emit_creates_nested_dir_and_persists(tmp_path):
    bus = str(tmp_path / "sub" / "dir" / "events.jsonl")
    record = emit(bus, "agent-1", "task-1", "TASK_COMPLETE", "done")
    assert os.path.isfile(bus)
    assert read_events(bus) == [record]


def test_delivery_is_at_least_once_not_exactly_once(tmp_path):
    bus = _bus(tmp_path)
    first = emit(bus, "agent-1", "task-1", "WORKER_PROGRESS", "half")
    second = emit(bus, "agent-1", "task-1", "WORKER_PROGRESS", "half")
    assert len(read_events(bus)) == 2
    state = {}
    for event in replay(bus):
        state[event["task_id"]] = event["event_type"]
    assert state == {"task-1": "WORKER_PROGRESS"}
    assert first != second  # distinct records (timestamps differ)


def test_scan_report_counts_valid_and_dropped(tmp_path):
    assert scan_report(str(tmp_path / "missing.jsonl")) == {
        "total": 0, "valid": 0, "dropped": 0}
    bus = _bus(tmp_path)
    emit(bus, "agent-1", "task-1", "TASK_COMPLETE", "done")
    with open(bus, "ab") as f:
        f.write(b"not json\n")
        f.write(b"\n")
        f.write(b'{"event_type": "NOPE"}\n')
    assert scan_report(bus) == {"total": 3, "valid": 1, "dropped": 2}


def test_emit_dir_fsync_failure_is_loud_but_persisted(tmp_path, monkeypatch):
    bus = str(tmp_path / "events.jsonl")
    real_fsync = os.fsync

    def fail_on_dirs(fd):
        if statmod.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("simulated dir-fsync failure")
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_on_dirs)
    with pytest.raises(OSError, match="simulated dir-fsync failure"):
        emit(bus, "agent-1", "task-1", "TASK_COMPLETE", "done")
    assert len(read_events(bus)) == 1


def test_read_revalidates_foreign_written_lines(tmp_path):
    bus = _bus(tmp_path)
    good = emit(bus, "agent-1", "task-1", "TASK_COMPLETE", "done")
    foreign_lines = [
        {"event_type": "NOPE", "agent_id": "a", "task_id": "t",
         "short_summary": "s", "timestamp": "2026-01-01T00:00:00+00:00"},
        {"event_type": ["TASK_COMPLETE"], "agent_id": "a", "task_id": "t",
         "short_summary": "s", "timestamp": "2026-01-01T00:00:00+00:00"},
        {"event_type": "TASK_COMPLETE", "task_id": "t",
         "short_summary": "s", "timestamp": "2026-01-01T00:00:00+00:00"},
        {"event_type": "TASK_COMPLETE", "agent_id": "a", "task_id": "t",
         "short_summary": "api_key=sk-live-123", "timestamp": "2026-01-01T00:00:00+00:00"},
        {"event_type": "TASK_COMPLETE", "agent_id": "a", "task_id": "t",
         "short_summary": "s"},
        {"event_type": "TASK_COMPLETE", "agent_id": "a", "task_id": "t",
         "short_summary": "s", "timestamp": "not-a-time"},
        {"event_type": "TASK_COMPLETE", "agent_id": "a", "task_id": "  t",
         "short_summary": "s", "timestamp": "2026-01-01T00:00:00+00:00"},
        {"event_type": "TASK_COMPLETE", "agent_id": "a", "task_id": "t",
         "short_summary": "s ", "timestamp": "2026-01-01T00:00:00+00:00"},
        "just a string",
        [1, 2],
    ]
    with open(bus, "ab") as f:
        for line in foreign_lines:
            blob = line if isinstance(line, str) else json.dumps(line)
            f.write((blob + "\n").encode("utf-8"))
    assert read_events(bus) == [good]
    assert list(replay(bus, task_id="task-1")) == [good]


def test_concurrent_appends_all_persisted(tmp_path):
    bus = _bus(tmp_path)
    threads = [
        threading.Thread(
            target=emit,
            args=(bus, f"a{i}", f"t{i}", "WORKER_PROGRESS", f"s{i}"),
        )
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    events = read_events(bus)
    assert len(events) == 8
    assert {e["task_id"] for e in events} == {f"t{i}" for i in range(8)}
