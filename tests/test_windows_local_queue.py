"""Windows-local queue over the canonical work queue. No provider, no network."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from courier_core.work_queue import WorkQueue, WorkQueueError

from scripts.windows_worker.local_queue import (
    TemporaryFailure,
    backoff_seconds,
    heartbeat,
    run_once,
    run_until_idle,
)

NOW = datetime(2026, 10, 23, 9, 0, 0, tzinfo=timezone.utc)
HOLDER = "windows:WIN-01"


def _item(item_id, scope, status="READY", depends=None):
    return {
        "id": item_id,
        "title": "Item " + item_id,
        "lane": "L6",
        "branch": "cursor/windows-lock-import-be3a",
        "files_scope": scope,
        "depends_on": depends or [],
        "acceptance": ["local file evidence"],
        "provider_hints": ["local"],
        "status": status,
        "lease": None,
    }


def _write_items(directory, rows):
    directory.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (directory / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")


def _queue(tmp_path, rows):
    home = tmp_path / "items"
    _write_items(home, rows)
    return WorkQueue(home, tmp_path / "ledger.jsonl")


def _execute(item_id, workspace):
    path = workspace / f"{item_id}.txt"
    path.write_text("done\n", encoding="utf-8")
    return path.name


def test_only_the_holder_can_claim_and_final_is_not_restarted(tmp_path):
    queue = _queue(tmp_path, [_item("A", ["scripts/windows_worker/a.py"])])
    other = run_once(queue, "other-host", "win-host", tmp_path / "other", _execute, NOW)
    assert other["outcome"] == "final" and other["item_id"] == "A"
    with pytest.raises(WorkQueueError) as caught:
        queue.claim("A", HOLDER, 60, now=NOW)
    assert caught.value.code == "NOT_CLAIMABLE"
    again = run_once(queue, HOLDER, "win-host", tmp_path / "again", _execute, NOW)
    assert again["outcome"] == "idle"


def test_checkpoint_releases_only_the_next_ready_workkey(tmp_path):
    queue = _queue(tmp_path, [
        _item("A", ["scripts/windows_worker/a.py"]),
        _item("B", ["scripts/windows_worker/b.py"], depends=["A"]),
        _item("C", ["scripts/windows_worker/c.py"], depends=["B"]),
    ])
    first = run_once(queue, HOLDER, "win-host", tmp_path / "work", _execute, NOW)
    assert first["outcome"] == "final"
    assert first["item_id"] == "A"
    assert first["next"] == ["B"]
    second = run_once(queue, HOLDER, "win-host", tmp_path / "work", _execute, NOW)
    assert second["item_id"] == "B" and second["next"] == ["C"]


def test_selection_is_deterministic_and_resumable(tmp_path):
    queue = _queue(tmp_path, [
        _item("C", ["scripts/windows_worker/c.py"]),
        _item("A", ["scripts/windows_worker/a.py"]),
        _item("B", ["scripts/windows_worker/b.py"]),
    ])
    seen = []

    def execute(item_id, workspace):
        seen.append(item_id)
        if item_id == "A":
            raise SystemExit("crash after claim")
        return _execute(item_id, workspace)

    try:
        run_once(queue, HOLDER, "win-host", tmp_path / "work", execute, NOW)
    except SystemExit:
        pass
    assert seen == ["A"]
    assert [item["id"] for item in queue.list_ready(now=NOW)] == ["B", "C"]
    resumed = []

    def execute_again(item_id, workspace):
        resumed.append(item_id)
        return _execute(item_id, workspace)

    receipt = run_once(queue, HOLDER, "win-host", tmp_path / "work", execute_again, NOW)
    assert resumed == ["A"]
    assert receipt["item_id"] == "A" and receipt["next"] == ["B", "C"]


def test_blocked_dependency_is_not_released(tmp_path):
    queue = _queue(tmp_path, [
        _item("A", ["scripts/windows_worker/a.py"], status="BLOCKED"),
        _item("B", ["scripts/windows_worker/b.py"], depends=["A"]),
    ])
    called = []
    receipt = run_once(queue, HOLDER, "win-host", tmp_path / "work", lambda item, ws: called.append(item), NOW)
    assert receipt["outcome"] == "idle"
    assert called == []
    assert queue.items(now=NOW)[0]["status"] == "BLOCKED"
    assert "B" not in [item["id"] for item in queue.list_ready(now=NOW)]


def test_temporary_failures_retry_then_dead_letter_keeps_the_claim(tmp_path):
    queue = _queue(tmp_path, [
        _item("A", ["scripts/windows_worker/a.py"]),
        _item("B", ["scripts/windows_worker/b.py"], depends=["A"]),
    ])
    calls = []

    def execute(item_id, workspace):
        calls.append(item_id)
        raise TemporaryFailure("disk busy")

    receipt = run_once(queue, HOLDER, "win-host", tmp_path / "work", execute, NOW, max_attempts=3)
    assert calls == ["A", "A", "A"]
    assert receipt["outcome"] == "dead_letter"
    assert receipt["reason"] == "ATTEMPTS_EXHAUSTED"
    dead = (tmp_path / "work" / "dead_letter.jsonl").read_text(encoding="utf-8")
    assert "\"item_id\": \"A\"" in dead
    assert "RELEASE" not in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    assert [item["id"] for item in queue.list_ready(now=NOW)] == []
    held = [item for item in queue.items(now=NOW) if item["id"] == "A"][0]
    assert held["status"] == "CLAIMED"
    assert held["lease"]["holder"] == HOLDER


def test_unverified_result_is_not_final(tmp_path):
    queue = _queue(tmp_path, [_item("A", ["scripts/windows_worker/a.py"])])

    def execute(item_id, workspace):
        return "missing.txt"

    receipt = run_once(queue, HOLDER, "win-host", tmp_path / "work", execute, NOW)
    assert receipt["outcome"] == "dead_letter" and receipt["reason"] == "UNVERIFIED"
    assert "RELEASE" not in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")


def test_receipt_log_symlink_is_not_followed(tmp_path):
    queue = _queue(tmp_path, [_item("A", ["scripts/windows_worker/a.py"])])
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside.log"
    (work / "receipts.jsonl").symlink_to(outside)
    receipt = run_once(queue, HOLDER, "win-host", work, _execute, NOW)
    assert receipt["outcome"] == "blocked" and receipt["reason"] == "RECEIPT_LINK"
    assert not outside.exists()
    ledger = tmp_path / "ledger.jsonl"
    assert not ledger.exists() or "RELEASE" not in ledger.read_text(encoding="utf-8")
    held = [item for item in queue.items(now=NOW) if item["id"] == "A"][0]
    assert held["status"] == "READY"


def test_ran_phase_survives_and_does_not_execute_again(tmp_path):
    queue = _queue(tmp_path, [_item("A", ["scripts/windows_worker/a.py"])])
    work = tmp_path / "work"
    queue.claim("A", HOLDER, 60, host="win-host", now=NOW)
    (work).mkdir()
    (work / "A.txt").write_text("done\n", encoding="utf-8")
    (work / "phase.json").write_text(json.dumps({
        "item_id": "A", "phase": "RAN", "evidence": "A.txt",
    }), encoding="utf-8")
    called = []
    receipt = run_once(queue, HOLDER, "win-host", work, lambda item, ws: called.append(item), NOW)
    assert called == []
    assert receipt["outcome"] == "final" and receipt["item_id"] == "A"


def test_remainder_stays_ready_after_a_new_queue_object(tmp_path):
    rows = [
        _item("A", ["scripts/windows_worker/a.py"]),
        _item("B", ["scripts/windows_worker/b.py"]),
    ]
    queue = _queue(tmp_path, rows)
    first = run_once(queue, HOLDER, "win-host", tmp_path / "work", _execute, NOW)
    assert first["item_id"] == "A"
    reopened = WorkQueue(tmp_path / "items", tmp_path / "ledger.jsonl")
    assert [item["id"] for item in reopened.list_ready(now=NOW)] == ["B"]
    second = run_once(reopened, HOLDER, "win-host", tmp_path / "work", _execute, NOW)
    assert second["item_id"] == "B" and second["next"] == []


def test_two_homes_cannot_both_dispatch_wq1(tmp_path):
    """WQ-1 stays with the home that claimed it. The other home does not run it."""
    queue = _queue(tmp_path, [_item("WQ-1", ["scripts/windows_worker/a.py"])])
    calls = []

    def execute(item_id, workspace):
        calls.append((item_id, Path(workspace).name))
        if Path(workspace).name == "home-a":
            raise SystemExit("home-a stopped after the claim")
        return _execute(item_id, workspace)

    try:
        run_once(queue, "home-a", "host-a", tmp_path / "home-a", execute, NOW)
    except SystemExit:
        pass
    other = run_once(queue, "home-b", "host-b", tmp_path / "home-b", execute, NOW)
    assert calls == [("WQ-1", "home-a")]
    assert other["outcome"] == "idle"
    held = [item for item in queue.items(now=NOW) if item["id"] == "WQ-1"][0]
    assert held["status"] == "CLAIMED" and held["lease"]["holder"] == "home-a"


def test_kill_switch_stops_a_retry_without_a_second_run(tmp_path):
    queue = _queue(tmp_path, [_item("A", ["scripts/windows_worker/a.py"])])
    calls = []

    def execute(item_id, workspace):
        calls.append(item_id)
        (workspace / "KILL").write_text("stop\n", encoding="utf-8")
        raise TemporaryFailure("disk busy")

    receipt = run_once(queue, HOLDER, "win-host", tmp_path / "work", execute, NOW, max_attempts=3)
    assert calls == ["A"]
    assert receipt["outcome"] == "killed" and receipt["item_id"] == "A"
    assert "RELEASE" not in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    held = [item for item in queue.items(now=NOW) if item["id"] == "A"][0]
    assert held["status"] == "CLAIMED"


def test_dead_letter_is_not_executed_or_released_again(tmp_path):
    queue = _queue(tmp_path, [_item("A", ["scripts/windows_worker/a.py"])])
    calls = []

    def execute(item_id, workspace):
        calls.append(item_id)
        raise TemporaryFailure("disk busy")

    work = tmp_path / "work"
    first = run_once(queue, HOLDER, "win-host", work, execute, NOW, max_attempts=2)
    assert first["outcome"] == "dead_letter"
    second = run_once(queue, HOLDER, "win-host", work, execute, NOW, max_attempts=2)
    assert second["outcome"] == "dead_letter" and second["reason"] == "ATTEMPTS_EXHAUSTED"
    assert calls == ["A", "A"]
    text = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    assert "RELEASE" not in text
    again = queue.release("A", HOLDER, "BLOCKED", now=NOW)
    repeat = queue.release("A", HOLDER, "BLOCKED", now=NOW)
    assert again["status"] == "DONE" and again["idempotent"] is False
    assert repeat["status"] == "DONE" and repeat["idempotent"] is True


def test_a_second_holder_does_not_take_the_claimed_workkey(tmp_path):
    queue = _queue(tmp_path, [_item("A", ["scripts/windows_worker/a.py"])])
    queue.claim("A", HOLDER, 60, host="win-host", now=NOW)
    called = []
    receipt = run_once(queue, "windows:WIN-02", "win-host", tmp_path / "other", lambda item, ws: called.append(item), NOW)
    assert receipt["outcome"] == "idle"
    assert called == []
    held = [item for item in queue.items(now=NOW) if item["id"] == "A"][0]
    assert held["lease"]["holder"] == HOLDER


def test_heartbeat_is_not_verification_and_kill_switch_stops_before_claim(tmp_path):
    work = tmp_path / "work"
    pulse = heartbeat(work)
    assert pulse == {"outcome": "alive", "verified": False}
    assert json.loads((work / "health.json").read_text(encoding="utf-8"))["verified"] is False
    (work / "KILL").write_text("stop\n", encoding="utf-8")
    queue = _queue(tmp_path, [_item("A", ["scripts/windows_worker/a.py"])])
    called = []
    receipts = run_until_idle(queue, HOLDER, "win-host", work, lambda item, ws: called.append(item), NOW)
    assert receipts == [{"outcome": "killed"}]
    assert called == []
    assert not (tmp_path / "ledger.jsonl").exists()
    assert backoff_seconds(0) == 10
    assert backoff_seconds(5) == 300
    assert backoff_seconds(8) == 300


def test_synthetic_run_finalizes_distinct_workkeys_in_order(tmp_path):
    queue = _queue(tmp_path, [
        _item("C", ["scripts/windows_worker/c.py"]),
        _item("A", ["scripts/windows_worker/a.py"]),
        _item("B", ["scripts/windows_worker/b.py"]),
    ])
    receipts = run_until_idle(queue, HOLDER, "win-host", tmp_path / "work", _execute, NOW)
    assert [item["outcome"] for item in receipts] == ["final", "final", "final", "idle"]
    assert [item.get("item_id") for item in receipts[:3]] == ["A", "B", "C"]
    ledger = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    assert ledger.count('"type":"RELEASE"') == 3
    assert ledger.count('"result":"FINAL"') == 3
    steps = [
        json.loads(line)["step"]
        for line in (tmp_path / "work" / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert steps[:5] == ["CLAIM", "RUN", "VERIFY", "FINAL", "NEXT"]
    for item_id in ("A", "B", "C"):
        assert (tmp_path / "work" / f"{item_id}.txt").read_text(encoding="utf-8") == "done\n"
