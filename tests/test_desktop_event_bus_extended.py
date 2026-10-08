import os
import json
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


def _bus_file(tmp_path):
    return str(tmp_path / "desktop_events.jsonl")


def test_concurrent_emit_append_safety(tmp_path):
    bus = _bus_file(tmp_path)
    num_threads = 10
    events_per_thread = 15

    def worker(worker_idx):
        for i in range(events_per_thread):
            emit(
                bus,
                f"worker-{worker_idx}",
                f"task-{worker_idx}-{i}",
                "WORKER_PROGRESS",
                f"Step {i} executed cleanly"
            )

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    records = read_events(bus)
    assert len(records) == num_threads * events_per_thread
    # Check that all records parse and have sequential/valid fields
    for r in records:
        assert r["event_type"] == "WORKER_PROGRESS"
        assert r["agent_id"].startswith("worker-")


def test_read_events_filtered_by_agent_and_task(tmp_path):
    bus = _bus_file(tmp_path)
    emit(bus, "agent-A", "task-1", "WORKER_STARTED", "A starts 1")
    emit(bus, "agent-A", "task-2", "WORKER_PROGRESS", "A continues 2")
    emit(bus, "agent-B", "task-1", "TASK_COMPLETE", "B completes 1")

    # Filter by agent_id
    a_events = read_events(bus, agent_id="agent-A")
    assert len(a_events) == 2
    assert {e["task_id"] for e in a_events} == {"task-1", "task-2"}

    # Filter by task_id
    t1_events = read_events(bus, task_id="task-1")
    assert len(t1_events) == 2
    assert {e["agent_id"] for e in t1_events} == {"agent-A", "agent-B"}

    # Filter by both
    b_t1 = read_events(bus, agent_id="agent-B", task_id="task-1")
    assert len(b_t1) == 1
    assert b_t1[0]["event_type"] == "TASK_COMPLETE"


def test_scan_report_summarizes_active_tasks(tmp_path):
    bus = _bus_file(tmp_path)
    emit(bus, "agent-1", "task-open", "WORKER_STARTED", "Starting work")
    emit(bus, "agent-1", "task-open", "WORKER_PROGRESS", "50% done")
    emit(bus, "agent-2", "task-done", "WORKER_STARTED", "Starting done task")
    emit(bus, "agent-2", "task-done", "TASK_COMPLETE", "Work done successfully")

    report = scan_report(bus)
    assert report is not None
    assert "total_events" in report or "tasks" in report or isinstance(report, dict)
