"""Crash between resume event and RESOLVED line: the next tick backfills exactly
one RESOLVED from the ledger, further ticks change nothing, no double effect."""

from collections import Counter

import pytest

from courier_worker import queue_feed
from scripts.coordination_ledger import EventType
from tests.test_blocked_wake_resume import _events, _inbox, _prepare
from tests.test_gate4_queue_restart_no_replay import _complete_posted, _queue_seq, _tick
from tests.test_ledger_v1_bridge import FakeHTTP


class Crash(Exception):
    pass


def test_crash_after_resume_before_resolved_is_backfilled_once(tmp_path, monkeypatch):
    home, queue, ledger, contract = _prepare(tmp_path)
    http = FakeHTTP()
    for _ in range(3):
        _tick(home, http)
    assert [r["kind"] for r in _inbox(home)] == ["NEEDS_YOU"]
    from courier_core.goal_contract import GoalContractStore
    GoalContractStore(home / "goal_contracts.jsonl").append(contract.confirm("person:founder", "2026-10-13T14:00:00Z"))

    real = queue_feed._append_line

    def crashing(path, record):
        if record.get("kind") == "RESOLVED":
            raise Crash("power loss before RESOLVED")
        return real(path, record)

    monkeypatch.setattr(queue_feed, "_append_line", crashing)
    with pytest.raises(Crash):
        _tick(home, http)
    resumes = [e for e in _events(home) if e.event_id.startswith("queue-resume-")]
    assert len(resumes) == 1                                  # resume event is durable
    assert [r["kind"] for r in _inbox(home)] == ["NEEDS_YOU"]  # RESOLVED missing

    monkeypatch.setattr(queue_feed, "_append_line", real)      # restart
    for _ in range(12):
        _tick(home, http)
        _complete_posted(http)
        if all(i["status"] == "DONE" for i in queue.items()):
            break
    inbox = _inbox(home)
    assert [r["kind"] for r in inbox] == ["NEEDS_YOU", "RESOLVED"], inbox
    assert (inbox[1]["mission_id"], inbox[1]["blocked_event_id"]) == (inbox[0]["mission_id"], inbox[0]["blocked_event_id"])
    assert inbox[1]["resume_event_id"] == resumes[0].event_id

    events = _events(home)
    assert len([e for e in events if e.event_id.startswith("queue-resume-")]) == 1
    counts = Counter((e.mission_id, e.event_type) for e in events)
    assert counts["WKA", EventType.FINAL] == 1 and counts["WKB", EventType.FINAL] == 1, counts
    assert sorted(p["params"]["unit"] for p in http.posts) == ["a", "b"]

    frozen = ((home / "coordination_ledger.jsonl").read_text(), list(http.posts), _queue_seq(ledger),
              (home / "run" / queue_feed.NEEDS_YOU_INBOX).read_text())
    for _ in range(3):
        _tick(home, http)
    assert ((home / "coordination_ledger.jsonl").read_text(), list(http.posts), _queue_seq(ledger),
            (home / "run" / queue_feed.NEEDS_YOU_INBOX).read_text()) == frozen
