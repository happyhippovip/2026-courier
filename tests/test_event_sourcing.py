"""Tests for courier_core.event_sourcing - Dual-Channel Event Sourcing & Real-time Replay Log."""

from __future__ import annotations

import json
import pytest

from courier_core.event_sourcing import (
    JournalEvent,
    EventStore,
    CorruptedEventLogError,
    main,
)


def test_append_and_sequential_ordering(tmp_path):
    store_path = tmp_path / "events.jsonl"
    store = EventStore(store_path)

    e1 = store.append(event_type="WORKER_CLAIMED", aggregate_id="task-101", data={"worker": "win-1"})
    e2 = store.append(event_type="STAGE_EXECUTED", aggregate_id="task-101", data={"step": 1})
    e3 = store.append(event_type="TASK_COMPLETED", aggregate_id="task-101", data={"status": "DONE"})

    assert e1.seq == 1
    assert e2.seq == 2
    assert e3.seq == 3
    assert e1.checksum != ""
    assert e2.checksum != ""


def test_dual_channel_realtime_subscriber(tmp_path):
    store_path = tmp_path / "events.jsonl"
    store = EventStore(store_path)

    received = []
    store.subscribe(lambda event: received.append(event))

    store.append(event_type="PING", aggregate_id="system", data={"val": 42})
    store.append(event_type="PONG", aggregate_id="system", data={"val": 43})

    assert len(received) == 2
    assert received[0].event_type == "PING"
    assert received[1].event_type == "PONG"


def test_replay_and_state_reconstruction(tmp_path):
    store_path = tmp_path / "events.jsonl"
    store = EventStore(store_path)

    store.append(event_type="TASK_CREATED", aggregate_id="task-A", data={"units": 10})
    store.append(event_type="TASK_CREATED", aggregate_id="task-B", data={"units": 20})
    store.append(event_type="TASK_UPDATED", aggregate_id="task-A", data={"units": 15})

    # Replay specific aggregate
    events_a = store.replay(aggregate_id="task-A")
    assert len(events_a) == 2
    assert events_a[0].event_type == "TASK_CREATED"
    assert events_a[1].data["units"] == 15

    # Replay all
    all_events = store.replay()
    assert len(all_events) == 3


def test_corrupted_event_detection(tmp_path):
    store_path = tmp_path / "events.jsonl"
    store = EventStore(store_path)

    store.append(event_type="ORDER_PLACED", aggregate_id="order-1", data={"amount": 100})

    # Tamper with file
    lines = store_path.read_text(encoding="utf-8").strip().splitlines()
    corrupt_data = json.loads(lines[0])
    corrupt_data["data"]["amount"] = 999999  # Tamper without updating checksum
    store_path.write_text(json.dumps(corrupt_data) + "\n", encoding="utf-8")

    # Reload store
    new_store = EventStore(store_path)
    with pytest.raises(CorruptedEventLogError, match="Checksum mismatch in event log"):
        new_store.replay()


def test_snapshot_compaction_and_delta_catchup(tmp_path):
    store_path = tmp_path / "events.jsonl"
    store = EventStore(store_path)

    store.append(event_type="COUNT_INC", aggregate_id="counter-1", data={"inc": 1})
    store.append(event_type="COUNT_INC", aggregate_id="counter-1", data={"inc": 2})

    # Create snapshot at seq 2
    snapshot = store.create_snapshot(aggregate_id="counter-1", state={"count": 3}, up_to_seq=2)
    assert snapshot.seq == 2
    assert snapshot.state == {"count": 3}

    # Subsequent delta event
    store.append(event_type="COUNT_INC", aggregate_id="counter-1", data={"inc": 4})

    # Catch up
    snap, deltas = store.get_snapshot_and_deltas(aggregate_id="counter-1")
    assert snap is not None
    assert snap.seq == 2
    assert len(deltas) == 1
    assert deltas[0].data["inc"] == 4


def test_cli_event_sourcing(tmp_path, monkeypatch, capsys):
    store_file = tmp_path / "events.jsonl"

    # Append
    monkeypatch.setattr(
        "sys.argv",
        [
            "event_sourcing.py",
            "append",
            "--store",
            str(store_file),
            "--type",
            "USER_LOGIN",
            "--aggregate",
            "user-101",
            "--data",
            '{"ip": "127.0.0.1"}',
        ],
    )
    main()

    # Replay
    monkeypatch.setattr(
        "sys.argv",
        [
            "event_sourcing.py",
            "replay",
            "--store",
            str(store_file),
            "--aggregate",
            "user-101",
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "USER_LOGIN" in out
    assert "user-101" in out
