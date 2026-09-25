"""Regression: stale-lease reconcile is fail-closed (Cannon-V1 Crash/Resume).

`work_queue reconcile --reclaim-stale` must BLOCK stale CLAIMED/RUNNING
tasks that hold no result (STALE_WORKER_EFFECT_AMBIGUOUS: replaying them
would risk a duplicate effect), always pop the stale lease, preserve
completed results for RESEND (never re-execute), and leave fresh leases
untouched.

Pure in-memory pin of `cmd_reconcile`: no state dir, no subprocess,
no network, deterministic clock.
"""
from types import SimpleNamespace

from scripts.work_queue import cmd_reconcile

NOW = 1_000_000.0
ARGS = SimpleNamespace(reclaim_stale=3600)


def stale_lease(worker="w1"):
    return {"worker": worker, "write_scopes": [], "claimed_at": NOW - 7200}


def fresh_lease(worker="w1"):
    return {"worker": worker, "write_scopes": [], "claimed_at": NOW - 10}


def test_stale_claimed_without_result_blocked_and_lease_popped():
    data = {
        "tasks": {"t1": {"task_id": "t1", "status": "CLAIMED", "owner": "w1"}},
        "leases": {"t1": stale_lease()},
    }
    out = cmd_reconcile(ARGS, data, NOW)
    assert out["reclaimed"] == ["t1"]
    assert data["tasks"]["t1"]["status"] == "BLOCKED"
    assert data["tasks"]["t1"]["block_reason"] == "STALE_WORKER_EFFECT_AMBIGUOUS"
    assert "owner" not in data["tasks"]["t1"]
    assert "t1" not in data["leases"]


def test_stale_running_without_result_blocked():
    data = {
        "tasks": {"t2": {"task_id": "t2", "status": "RUNNING", "owner": "w1"}},
        "leases": {"t2": stale_lease()},
    }
    out = cmd_reconcile(ARGS, data, NOW)
    assert out["reclaimed"] == ["t2"]
    assert data["tasks"]["t2"]["status"] == "BLOCKED"
    assert "t2" not in data["leases"]


def test_stale_lease_with_result_preserved_for_resend():
    result = {"result_id": "result-abc", "outcome": "ok"}
    data = {
        "tasks": {"t3": {"task_id": "t3", "status": "CLAIMED", "result": result}},
        "leases": {"t3": stale_lease()},
    }
    out = cmd_reconcile(ARGS, data, NOW)
    assert out["reclaimed"] == []
    assert data["tasks"]["t3"]["status"] == "CLAIMED"
    assert data["tasks"]["t3"]["result"] == result
    assert "t3" not in data["leases"]


def test_done_task_keeps_status_lease_popped():
    data = {
        "tasks": {"t4": {"task_id": "t4", "status": "DONE"}},
        "leases": {"t4": stale_lease()},
    }
    out = cmd_reconcile(ARGS, data, NOW)
    assert out["reclaimed"] == []
    assert data["tasks"]["t4"]["status"] == "DONE"
    assert "t4" not in data["leases"]


def test_fresh_lease_untouched():
    data = {
        "tasks": {"t5": {"task_id": "t5", "status": "CLAIMED", "owner": "w1"}},
        "leases": {"t5": fresh_lease()},
    }
    out = cmd_reconcile(ARGS, data, NOW)
    assert out["reclaimed"] == []
    assert data["tasks"]["t5"]["status"] == "CLAIMED"
    assert "t5" in data["leases"]
