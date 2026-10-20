import json
import pytest
from pathlib import Path
from courier_core.event_bus import (
    Event,
    EventBus,
    OverflowPolicy,
    BufferOverflowError,
    match_topic_pattern,
)


def test_topic_pattern_matching():
    # Exact
    assert match_topic_pattern("lane.L1.dispatch", "lane.L1.dispatch") is True
    assert match_topic_pattern("lane.L1.dispatch", "lane.L2.dispatch") is False

    # Single-token wildcard (*)
    assert match_topic_pattern("lane.*.dispatch", "lane.L1.dispatch") is True
    assert match_topic_pattern("lane.*.dispatch", "lane.L2.dispatch") is True
    assert match_topic_pattern("lane.*.dispatch", "lane.L1.sub.dispatch") is False

    # Multi-token wildcard (#)
    assert match_topic_pattern("worker.#", "worker.win") is True
    assert match_topic_pattern("worker.#", "worker.win.status.pulse") is True
    assert match_topic_pattern("worker.#", "worker") is True
    assert match_topic_pattern("worker.#", "lane.worker.win") is False


def test_exact_publish_and_subscribe():
    bus = EventBus()
    received = []

    def on_event(ev: Event):
        received.append(ev)

    sub_id = bus.subscribe("lane.L1.dispatch", on_event)
    assert sub_id != ""

    ev = Event(
        event_id="ev-1",
        topic="lane.L1.dispatch",
        payload={"work_item": "P10"},
        sender="dispatcher-1"
    )
    bus.publish(ev)

    assert len(received) == 1
    assert received[0].event_id == "ev-1"
    assert received[0].payload["work_item"] == "P10"


def test_wildcard_dispatch_to_multiple_subscribers():
    bus = EventBus()
    all_events = []
    win_events = []

    bus.subscribe("#", lambda ev: all_events.append(ev))
    bus.subscribe("worker.win.*", lambda ev: win_events.append(ev))

    ev1 = Event(event_id="e1", topic="worker.win.heartbeat", payload={"status": "OK"})
    ev2 = Event(event_id="e2", topic="worker.linux.heartbeat", payload={"status": "OK"})
    ev3 = Event(event_id="e3", topic="lane.L1.dispatch", payload={"item": "X"})

    bus.publish(ev1)
    bus.publish(ev2)
    bus.publish(ev3)

    assert len(all_events) == 3
    assert len(win_events) == 1
    assert win_events[0].event_id == "e1"


def test_subscriber_exception_isolated_and_sent_to_dlq():
    bus = EventBus()
    success_received = []

    def faulty_sub(ev: Event):
        raise RuntimeError("Subscriber crashed processing event")

    bus.subscribe("test.topic", faulty_sub)
    bus.subscribe("test.topic", lambda ev: success_received.append(ev))

    ev = Event(event_id="e-crash", topic="test.topic", payload={"data": 123})
    bus.publish(ev)

    # The healthy subscriber still ran
    assert len(success_received) == 1

    # Faulty invocation captured in DLQ
    dlq = bus.get_dlq()
    assert len(dlq) == 1
    assert dlq[0]["event_id"] == "e-crash"
    assert "Subscriber crashed" in dlq[0]["error"]


def test_buffer_overflow_policies():
    # Policy: RAISE
    bus_raise = EventBus(max_buffer_size=2, overflow_policy=OverflowPolicy.RAISE)
    bus_raise.publish(Event(event_id="1", topic="t", payload={}))
    bus_raise.publish(Event(event_id="2", topic="t", payload={}))
    with pytest.raises(BufferOverflowError):
        bus_raise.publish(Event(event_id="3", topic="t", payload={}))

    # Policy: DROP_OLDEST
    bus_drop = EventBus(max_buffer_size=2, overflow_policy=OverflowPolicy.DROP_OLDEST)
    bus_drop.publish(Event(event_id="1", topic="t", payload={"seq": 1}))
    bus_drop.publish(Event(event_id="2", topic="t", payload={"seq": 2}))
    bus_drop.publish(Event(event_id="3", topic="t", payload={"seq": 3}))

    history = bus_drop.get_recent_events()
    assert len(history) == 2
    assert history[0].event_id == "2"
    assert history[1].event_id == "3"


def test_journal_persistence_and_replay(tmp_path):
    journal_path = tmp_path / "events.jsonl"
    bus = EventBus(journal_path=journal_path)

    ev1 = Event(event_id="j1", topic="audit.log", payload={"action": "login"})
    ev2 = Event(event_id="j2", topic="audit.log", payload={"action": "logout"})

    bus.publish(ev1)
    bus.publish(ev2)

    assert journal_path.exists()
    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    # Replay
    replayed_events = EventBus.replay_journal(journal_path)
    assert len(replayed_events) == 2
    assert replayed_events[0].event_id == "j1"
    assert replayed_events[1].event_id == "j2"


def test_cli_invocation(tmp_path):
    import subprocess
    import sys

    journal_file = tmp_path / "cli_events.jsonl"

    # Publish via CLI
    cmd_pub = [
        sys.executable,
        "-m",
        "courier_core.event_bus",
        "publish",
        "--journal",
        str(journal_file),
        "--topic",
        "cli.test.topic",
        "--payload",
        json.dumps({"key": "val"}),
        "--sender",
        "cli-runner",
    ]
    proc_pub = subprocess.run(cmd_pub, capture_output=True, text=True, check=True)
    out_pub = json.loads(proc_pub.stdout)
    assert out_pub["status"] == "PUBLISHED"
    assert out_pub["topic"] == "cli.test.topic"

    # Inspect via CLI
    cmd_insp = [
        sys.executable,
        "-m",
        "courier_core.event_bus",
        "inspect",
        "--journal",
        str(journal_file),
    ]
    proc_insp = subprocess.run(cmd_insp, capture_output=True, text=True, check=True)
    out_insp = json.loads(proc_insp.stdout)
    assert out_insp["total_events"] == 1
    assert out_insp["events"][0]["topic"] == "cli.test.topic"
