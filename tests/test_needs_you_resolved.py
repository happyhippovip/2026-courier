"""needs_you.jsonl: RESOLVED closes a NEEDS_YOU line append-only and idempotently;
old readers (dedup keys) keep working. Synthetic only."""

import json

from courier_worker import queue_feed
from tests.test_blocked_wake_resume import _inbox, _prepare
from tests.test_gate4_queue_restart_no_replay import _complete_posted, _tick
from tests.test_ledger_v1_bridge import FakeHTTP


def _block_then_confirm(tmp_path):
    home, queue, ledger, contract = _prepare(tmp_path)
    http = FakeHTTP()
    for _ in range(3):
        _tick(home, http)
    assert [r["kind"] for r in _inbox(home)] == ["NEEDS_YOU"]
    from courier_core.goal_contract import GoalContractStore
    GoalContractStore(home / "goal_contracts.jsonl").append(contract.confirm("person:founder", "2026-10-13T14:00:00Z"))
    return home, http


def test_resume_appends_one_resolved_and_is_idempotent(tmp_path):
    home, http = _block_then_confirm(tmp_path)
    raw_before = (home / "run" / queue_feed.NEEDS_YOU_INBOX).read_text(encoding="utf-8")
    for _ in range(8):
        _tick(home, http)
        _complete_posted(http)
    raw = (home / "run" / queue_feed.NEEDS_YOU_INBOX).read_text(encoding="utf-8")
    assert raw.startswith(raw_before)                      # append-only
    rows = _inbox(home)
    assert [r["kind"] for r in rows] == ["NEEDS_YOU", "RESOLVED"]
    assert {k: rows[1][k] for k in ("mission_id", "blocked_event_id")} == \
           {k: rows[0][k] for k in ("mission_id", "blocked_event_id")}


def test_existing_resolved_is_not_duplicated(tmp_path):
    home, http = _block_then_confirm(tmp_path)
    path = home / "run" / queue_feed.NEEDS_YOU_INBOX
    first = _inbox(home)[0]
    path.write_text(path.read_text(encoding="utf-8") + json.dumps(
        {"kind": "RESOLVED", "mission_id": first["mission_id"], "blocked_event_id": first["blocked_event_id"]}) + "\n",
        encoding="utf-8")
    for _ in range(4):
        _tick(home, http)
        _complete_posted(http)
    assert [r["kind"] for r in _inbox(home)] == ["NEEDS_YOU", "RESOLVED"]


def test_old_reader_tolerates_resolved_lines(tmp_path):
    p = tmp_path / "needs_you.jsonl"
    p.write_text(json.dumps({"kind": "NEEDS_YOU", "mission_id": "M", "blocked_event_id": "e1"}) + "\n"
                 + json.dumps({"kind": "RESOLVED", "mission_id": "M", "blocked_event_id": "e1"}) + "\n",
                 encoding="utf-8")
    assert queue_feed._inbox_keys(p) == {"M|e1"}          # old dedup reader unchanged
    assert queue_feed._resolved_keys(p) == {"M|e1"}
