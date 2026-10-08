"""Real-mode MCP output matches the receipt read model, and bad ledgers fail closed."""

import json
import sqlite3

from courier_core.receipt_read_model import MAX_FILE_BYTES, ReceiptReadModel
from courier_mcp.state import RESULTS_NAME, STATE_NAME
from courier_mcp.tools import Source, call_tool

GOAL = "goal.mcp.1"


def _mission(task_id, status, when, goal=GOAL, result=None, reason=None):
    return {
        "task_id": task_id,
        "claim_event_id": "claim-" + task_id,
        "accepted_result_id": result,
        "status": status,
        "reason": reason,
        "evidence_ref": "task_id=" + task_id,
        "goal_id": goal,
        "goal_fingerprint": "a" * 64,
        "updated_at": when,
        "posted": status != "ERROR",
        "attempt": 1,
        "idempotency_key": "ledger:claim-" + task_id,
    }


def _write_bridge(home, missions):
    home.mkdir(parents=True, exist_ok=True)
    (home / STATE_NAME).write_text(json.dumps({"missions": missions}), encoding="utf-8")


def _write_results(home, rows):
    home.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(home / RESULTS_NAME)
    conn.execute(
        "CREATE TABLE events (seq INTEGER PRIMARY KEY, type TEXT, task_id TEXT, "
        "attempt INTEGER, dispatch_id TEXT, result_id TEXT, ts_utc TEXT, payload TEXT)"
    )
    conn.executemany(
        "INSERT INTO events (type, task_id, attempt, dispatch_id, result_id, ts_utc, payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _names(home):
    return sorted(path.name for path in home.iterdir()) if home.exists() else []


def test_real_mode_equals_receipt_read_model(tmp_path):
    home = tmp_path / "home"
    _write_bridge(home, {
        "B": _mission("task-b", "BLOCKED", "2026-10-08T02:00:00Z", reason="CONTROLLER_BLOCKED"),
        "A": _mission("task-a", "FINAL_DONE", "2026-10-08T01:00:00Z", result="result-a"),
        "C": _mission("task-c", "ERROR", "2026-10-08T03:00:00Z", goal="goal.other", reason="FAILED"),
        "D": _mission("task-d", "POSTED", "2026-10-08T04:00:00Z"),
    })
    _write_results(home, [
        ("RESULT_ACCEPTED", "task-a", 1, "dsp-a", "result-a", "2026-10-08T01:00:01Z",
         json.dumps({"outcome": "success"})),
        ("RESULT_READY", "task-a", 1, "dsp-a", "result-other", "2026-10-08T01:00:00Z",
         json.dumps({"outcome": "success"})),
        ("RESULT_ACCEPTED", "task-c", 1, "dsp-c", "result-not-accepted", "2026-10-08T03:00:01Z",
         json.dumps({"outcome": "failure"})),
    ])
    before = (home / STATE_NAME).read_bytes()
    db_before = (home / RESULTS_NAME).read_bytes()
    names = _names(home)
    source = Source(state_dir=home)
    model = ReceiptReadModel(home)
    listed = model.list_receipts()
    summary = model.summary()

    missions = call_tool(source, "list_missions", {"limit": 100})
    receipts = call_tool(source, "list_receipts", {"limit": 100})
    summed = call_tool(source, "receipts_summary", {})
    one = call_tool(source, "get_mission", {"mission_id": "A"})

    assert missions["readable"] is True and missions["source"] == "OK"
    assert missions["missions"] == listed["receipts"]
    assert receipts["receipts"] == listed["receipts"]
    assert receipts["total"] == len(listed["receipts"])
    assert one["found"] is True and one["mission"] == model.receipt("task-a")["receipt"]
    assert one["mission"]["result"] == {
        "attempt": 1,
        "dispatch_id": "dsp-a",
        "outcome": "success",
        "result_id": "result-a",
        "task_id": "task-a",
        "ts_utc": "2026-10-08T01:00:01Z",
    }
    assert summed["counts"] == summary["counts"]
    assert summed["total"] == summary["total"]
    assert summed["last_updated"] == summary["last_updated"] == "2026-10-08T04:00:00Z"
    assert summed["bridge"] == summary["bridge"] == "OK"
    assert summed["results"] == summary["results"] == "OK"
    blob = json.dumps(missions) + json.dumps(receipts) + json.dumps(summed) + json.dumps(one)
    assert str(home) not in blob
    assert (home / STATE_NAME).read_bytes() == before
    assert (home / RESULTS_NAME).read_bytes() == db_before
    assert _names(home) == names


def test_malformed_ledgers_fail_closed(tmp_path):
    home = tmp_path / "home"
    cases = [
        "{",
        json.dumps([]),
        json.dumps({"missions": {"A": {"task_id": "task-a"}, "B": {"task_id": "task-a"}}}),
        json.dumps({"missions": {"A": {"task_id": 5}}}),
        json.dumps({"missions": {}, "extra": 1}),
    ]
    for content in cases:
        case_home = home / str(abs(hash(content)))
        case_home.mkdir(parents=True)
        (case_home / STATE_NAME).write_text(content, encoding="utf-8")
        _assert_unreadable(case_home)


def test_unreadable_journal_fails_closed(tmp_path):
    home = tmp_path / "home"
    _write_bridge(home, {"A": _mission("task-a", "POSTED", "2026-10-08T01:00:00Z")})
    (home / RESULTS_NAME).write_bytes(b"not a database")
    _assert_unreadable(home)


def test_oversized_bridge_fails_closed(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / STATE_NAME).write_bytes(b" " * (MAX_FILE_BYTES + 1))
    _assert_unreadable(home)


def _assert_unreadable(home):
    source = Source(state_dir=home)
    model = ReceiptReadModel(home)
    listed = model.list_receipts()
    summary = model.summary()
    missions = call_tool(source, "list_missions", {})
    receipts = call_tool(source, "list_receipts", {})
    summed = call_tool(source, "receipts_summary", {})
    assert listed["readable"] is False and listed["receipts"] == []
    assert summary["readable"] is False and summary["total"] == 0
    assert missions["readable"] is False and missions["source"] == "UNREADABLE"
    assert missions["missions"] == [] and missions["total"] == 0
    assert receipts["receipts"] == [] and receipts["total"] == 0
    assert summed["readable"] is False
    assert summed["counts"] == summary["counts"]
    assert summed["total"] == summary["total"] == 0
    assert summed["last_updated"] is None
    assert summed["bridge"] == summary["bridge"]
    assert summed["results"] == summary["results"]
    blob = json.dumps(missions) + json.dumps(receipts) + json.dumps(summed)
    assert str(home) not in blob
