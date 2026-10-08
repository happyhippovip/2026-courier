import sqlite3
import pytest

from courier_core.events import Event, EventType
from courier_core.projection import (
    ProjectionError,
    apply_event,
    create_schema,
    fold,
    is_current,
    last_seq,
    load_task,
    load_tasks,
    projection_hash,
    rebuild_in_place,
)
from courier_core.state_machine import TaskStatus


def make_events():
    e1 = Event(
        type=EventType.TASK_CREATED,
        task_id="task-001",
        payload={
            "adapter": "test_adapter",
            "params": {"query": "hello"},
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 30,
        },
        seq=1,
    )
    e2 = Event(
        type=EventType.TASK_CLAIMED,
        task_id="task-001",
        attempt=1,
        dispatch_id="disp-001",
        worker_id="worker-001",
        payload={"ttl_s": 30},
        seq=2,
    )
    e3 = Event(
        type=EventType.TASK_STARTED,
        task_id="task-001",
        attempt=1,
        dispatch_id="disp-001",
        worker_id="worker-001",
        payload={},
        seq=3,
    )
    return [e1, e2, e3]


def test_create_schema_and_is_current():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    assert is_current(conn) is True
    assert last_seq(conn) == 0


def test_apply_event_and_load_task():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    events = make_events()
    for ev in events:
        apply_event(conn, ev)

    assert last_seq(conn) == 3

    task = load_task(conn, "task-001")
    assert task is not None
    assert task.task_id == "task-001"
    assert task.status == TaskStatus.RUNNING
    assert task.attempt == 1
    assert task.dispatch_id == "disp-001"
    assert task.worker_id == "worker-001"
    assert task.params == {"query": "hello"}

    tasks_running = load_tasks(conn, status=TaskStatus.RUNNING.value)
    assert len(tasks_running) == 1
    assert tasks_running[0].task_id == "task-001"

    tasks_queued = load_tasks(conn, status=TaskStatus.QUEUED.value)
    assert len(tasks_queued) == 0


def test_projection_hash_stable_against_system_events():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    for ev in make_events():
        apply_event(conn, ev)

    hash1 = projection_hash(conn)

    # Controller lifecycle event only advances seq
    sys_event = Event(type=EventType.CONTROLLER_STARTED, seq=4)
    apply_event(conn, sys_event)

    assert last_seq(conn) == 4
    hash2 = projection_hash(conn)
    assert hash1 == hash2  # Fingerprint unaffected by controller lifecycle


def test_rebuild_in_place_and_in_memory_fold():
    events = make_events()
    mem_fold = fold(events)
    assert "task-001" in mem_fold
    assert mem_fold["task-001"].status == TaskStatus.RUNNING

    conn = sqlite3.connect(":memory:")
    rebuild_in_place(conn, events)
    assert last_seq(conn) == 3

    task_sql = load_task(conn, "task-001")
    assert task_sql == mem_fold["task-001"]


def test_unsealed_event_raises_projection_error():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)

    unsealed = Event(
        type=EventType.TASK_CREATED,
        task_id="t-unsealed",
        payload={
            "adapter": "test",
            "params": {},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 10,
        },
        seq=None,
    )
    with pytest.raises(ProjectionError, match="only sealed events"):
        apply_event(conn, unsealed)
