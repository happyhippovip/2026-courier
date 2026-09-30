import json
import os
import threading

import pytest

from courier_overlay import (
    EVENT_TYPES,
    EventBusError,
    emit,
    read_events,
    replay,
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
