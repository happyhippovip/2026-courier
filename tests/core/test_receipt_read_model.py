"""Read-only receipt model. No provider, no bridge process, no writes."""

import json
import sqlite3
from pathlib import Path

from courier_core.receipt_read_model import MAX_FILE_BYTES, RECEIPT_FIELDS, ReceiptReadModel

GOAL = "goal.receipt.1"


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


def _write_bridge(home: Path, missions):
    home.mkdir(parents=True, exist_ok=True)
    (home / "ledger_bridge_state.json").write_text(
        json.dumps({"missions": missions}), encoding="utf-8")


def _write_results(home: Path, rows):
    home.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(home / "courier.db")
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


def _names(home: Path):
    return sorted(path.name for path in home.iterdir()) if home.exists() else []


def test_empty_home_is_readable_and_writes_nothing(tmp_path):
    model = ReceiptReadModel(tmp_path)
    before = _names(tmp_path)
    listed = model.list_receipts()
    assert listed == {
        "readable": True,
        "bridge": "ABSENT",
        "results": "ABSENT",
        "receipts": [],
    }
    summary = model.summary()
    assert summary["readable"] is True
    assert summary["counts"] == {"BLOCKED": 0, "ERROR": 0, "FINAL_DONE": 0, "POSTED": 0, "UNSET": 0}
    assert summary["total"] == 0
    assert summary["last_updated"] is None
    one = model.receipt("task-a")
    assert one["found"] is False and one["receipt"] is None
    assert _names(tmp_path) == before


def test_mixed_statuses_filters_and_verified_result(tmp_path):
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
    before = (home / "ledger_bridge_state.json").read_bytes()
    db_before = (home / "courier.db").read_bytes()
    names = _names(home)
    model = ReceiptReadModel(home)

    listed = model.list_receipts()
    assert listed["readable"] is True
    assert listed["bridge"] == "OK"
    assert listed["results"] == "OK"
    assert [item["task_id"] for item in listed["receipts"]] == ["task-a", "task-b", "task-c", "task-d"]
    assert [item["status"] for item in listed["receipts"]] == ["FINAL_DONE", "BLOCKED", "ERROR", "POSTED"]
    assert set(listed["receipts"][0]) == set(RECEIPT_FIELDS)
    done = listed["receipts"][0]
    assert done["result"] == {
        "attempt": 1,
        "dispatch_id": "dsp-a",
        "outcome": "success",
        "result_id": "result-a",
        "task_id": "task-a",
        "ts_utc": "2026-10-08T01:00:01Z",
    }
    assert listed["receipts"][1]["result"] is None
    assert listed["receipts"][2]["result"] is None

    blocked = model.list_receipts(status="BLOCKED")
    assert [item["task_id"] for item in blocked["receipts"]] == ["task-b"]
    same_goal = model.list_receipts(goal_id=GOAL)
    assert [item["task_id"] for item in same_goal["receipts"]] == ["task-a", "task-b", "task-d"]
    window = model.list_receipts(since="2026-10-08T02:00:00Z", until="2026-10-08T03:00:00Z")
    assert [item["task_id"] for item in window["receipts"]] == ["task-b", "task-c"]
    assert model.list_receipts(since="not-a-time")["receipts"] == []
    assert model.list_receipts(since="not-a-time")["filter"] == "INVALID"

    one = model.receipt("task-a")
    assert one["found"] is True
    assert one["receipt"]["mission_id"] == "A"
    assert one["receipt"]["evidence_ref"] == "task_id=task-a"
    assert model.receipt("missing")["found"] is False

    summary = model.summary()
    assert summary["counts"] == {"BLOCKED": 1, "ERROR": 1, "FINAL_DONE": 1, "POSTED": 1, "UNSET": 0}
    assert summary["total"] == 4
    assert summary["last_updated"] == "2026-10-08T04:00:00Z"
    blob = json.dumps(listed) + json.dumps(summary) + json.dumps(one)
    assert "HEALTHY" not in blob
    assert str(home) not in blob
    assert (home / "ledger_bridge_state.json").read_bytes() == before
    assert (home / "courier.db").read_bytes() == db_before
    assert _names(home) == names


def test_mission_list_shape_is_readable(tmp_path):
    home = tmp_path / "home"
    _write_bridge(home, [
        {**_mission("task-a", "POSTED", "2026-10-08T01:00:00Z"), "mission_id": "A"},
    ])
    listed = ReceiptReadModel(home).list_receipts()
    assert listed["readable"] is True
    assert listed["receipts"][0]["mission_id"] == "A"
    assert listed["receipts"][0]["status"] == "POSTED"


def test_malformed_bridge_or_results_are_unreadable(tmp_path):
    cases = [
        "{",
        "[]",
        json.dumps({"missions": "nope"}),
        json.dumps({"missions": {"A": []}}),
        json.dumps({"missions": {"A": {"status": "POSTED"}}}),
        json.dumps({"missions": {"A": {"task_id": "task-a", "status": 1}}}),
        json.dumps({"missions": {"A": {"task_id": "task-a"}, "B": {"task_id": "task-a"}}}),
        json.dumps({"missions": {}, "extra": 1}),
    ]
    for index, text in enumerate(cases):
        home = tmp_path / f"bridge-{index}"
        home.mkdir()
        (home / "ledger_bridge_state.json").write_text(text, encoding="utf-8")
        listed = ReceiptReadModel(home).list_receipts()
        assert listed["readable"] is False, text
        assert listed["bridge"] == "UNREADABLE"
        assert listed["receipts"] == []
        summary = ReceiptReadModel(home).summary()
        assert summary["total"] == 0
        assert summary["counts"]["POSTED"] == 0
        assert ReceiptReadModel(home).receipt("task-a")["found"] is False

    home = tmp_path / "results"
    _write_bridge(home, {"A": _mission("task-a", "POSTED", "2026-10-08T01:00:00Z")})
    (home / "courier.db").write_bytes(b"this is not a database")
    listed = ReceiptReadModel(home).list_receipts()
    assert listed["readable"] is False
    assert listed["bridge"] == "OK"
    assert listed["results"] == "UNREADABLE"
    assert listed["receipts"] == []


def test_oversized_files_are_unreadable(tmp_path):
    home = tmp_path / "bridge"
    home.mkdir()
    (home / "ledger_bridge_state.json").write_bytes(b"{" + b"x" * MAX_FILE_BYTES)
    listed = ReceiptReadModel(home).list_receipts()
    assert listed["readable"] is False
    assert listed["bridge"] == "UNREADABLE"
    assert listed["receipts"] == []

    home = tmp_path / "results"
    _write_bridge(home, {"A": _mission("task-a", "POSTED", "2026-10-08T01:00:00Z")})
    (home / "courier.db").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    listed = ReceiptReadModel(home).list_receipts()
    assert listed["readable"] is False
    assert listed["results"] == "UNREADABLE"
    assert listed["receipts"] == []
