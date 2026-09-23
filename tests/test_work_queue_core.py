"""Core correctness tests for scripts/work_queue.py.

Covers:
  - reconcile(): dependency-based WAITING→READY promotion
  - cmd_reconcile(): stale-lease recovery
  - cmd_block(): task blocking and lease release
  - Scope-clash prevention: two workers cannot hold the same write scope
  - Dependency chain: T2 activates when T1 completes
  - live_scopes(): staleness threshold
  - cmd_complete(): VERIFYING vs DONE based on stage
  - NOT_REQUIRED tasks are never reactivated by reconcile
"""

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO / "scripts"))

import work_queue as wq


# ─── Helpers ────────────────────────────────────────────────────────────────

def _task(tid, status="READY", deps=None, write_scopes=None, priority=1):
    return {
        "task_id": tid,
        "package_id": "P",
        "description": tid,
        "dependencies": deps or [],
        "read_scopes": [],
        "write_scopes": write_scopes or [],
        "status": status,
        "priority": priority,
    }


def _fresh_data(*tasks):
    return {"packages": {}, "tasks": {t["task_id"]: t for t in tasks}, "leases": {}}


def _args(**kw):
    defaults = {"worker": "w1", "caps": "", "package": "", "lease_ttl": 3600}
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _claim_args(worker="w1", caps="", package="", lease_ttl=3600):
    return _args(worker=worker, caps=caps, package=package, lease_ttl=lease_ttl)


# ─── reconcile() ────────────────────────────────────────────────────────────

def test_reconcile_waiting_becomes_ready_when_dep_done():
    t1 = _task("T1", status="DONE")
    t2 = _task("T2", status="WAITING", deps=["T1"])
    data = _fresh_data(t1, t2)
    changed = wq.reconcile(data, time.time())
    assert "T2" in changed
    assert data["tasks"]["T2"]["status"] == "READY"


def test_reconcile_waits_if_dep_not_done():
    t1 = _task("T1", status="RUNNING")
    t2 = _task("T2", status="WAITING", deps=["T1"])
    data = _fresh_data(t1, t2)
    changed = wq.reconcile(data, time.time())
    assert changed == []
    assert data["tasks"]["T2"]["status"] == "WAITING"


def test_reconcile_chain_of_three():
    """T3 depends on T2, T2 depends on T1. Completing T1 only activates T2."""
    t1 = _task("T1", status="DONE")
    t2 = _task("T2", status="WAITING", deps=["T1"])
    t3 = _task("T3", status="WAITING", deps=["T2"])
    data = _fresh_data(t1, t2, t3)
    changed = wq.reconcile(data, time.time())
    assert "T2" in changed
    assert "T3" not in changed
    assert data["tasks"]["T3"]["status"] == "WAITING"


def test_reconcile_not_required_never_reactivates():
    """Tasks blocked with NOT_REQUIRED must be permanently eliminated."""
    t1 = _task("T1", status="DONE")
    t2 = _task("T2", status="BLOCKED", deps=["T1"])
    t2["block_reason"] = "NOT_REQUIRED: superseded"
    data = _fresh_data(t1, t2)
    changed = wq.reconcile(data, time.time())
    assert "T2" not in changed
    assert data["tasks"]["T2"]["status"] == "BLOCKED"


def test_reconcile_blocked_with_other_reason_reactivates():
    """Tasks BLOCKED for reasons other than NOT_REQUIRED CAN become READY."""
    t1 = _task("T1", status="DONE")
    t2 = _task("T2", status="BLOCKED", deps=["T1"])
    t2["block_reason"] = "TRANSIENT_ERROR"
    data = _fresh_data(t1, t2)
    changed = wq.reconcile(data, time.time())
    assert "T2" in changed
    assert data["tasks"]["T2"]["status"] == "READY"


# ─── cmd_claim(): scope-clash prevention ────────────────────────────────────

def test_scope_clash_prevents_second_claim():
    """Two workers must not hold the same write scope simultaneously."""
    t1 = _task("T1", write_scopes=["scope/A"])
    t2 = _task("T2", write_scopes=["scope/A"])
    data = _fresh_data(t1, t2)
    now = time.time()

    # Worker 1 claims T1
    out1 = wq.cmd_claim(_claim_args(worker="w1"), data, now)
    assert out1["claimed"] in ("T1", "T2")
    first = out1["claimed"]
    second = "T2" if first == "T1" else "T1"

    # Worker 2 cannot claim the other task (same scope)
    out2 = wq.cmd_claim(_claim_args(worker="w2"), data, now)
    assert out2["claimed"] is None, f"scope clash: both {first} and {second} claimed"


def test_disjoint_scopes_allow_concurrent_claims():
    t1 = _task("T1", write_scopes=["scope/A"])
    t2 = _task("T2", write_scopes=["scope/B"])
    data = _fresh_data(t1, t2)
    now = time.time()

    out1 = wq.cmd_claim(_claim_args(worker="w1"), data, now)
    assert out1["claimed"] is not None
    out2 = wq.cmd_claim(_claim_args(worker="w2"), data, now)
    assert out2["claimed"] is not None
    assert out1["claimed"] != out2["claimed"]


# ─── cmd_complete(): stage determines final status ───────────────────────────

def test_complete_accepted_stage_sets_done():
    t1 = _task("T1", status="CLAIMED")
    data = _fresh_data(t1)
    args = SimpleNamespace(task_id="T1", result_json=json.dumps({"result_id": "r1"}), stage="ACCEPTED")
    out = wq.cmd_complete(args, data, time.time())
    assert out["done"] == "T1"
    assert data["tasks"]["T1"]["status"] == "DONE"


def test_complete_non_accepted_stage_sets_verifying():
    t1 = _task("T1", status="CLAIMED")
    data = _fresh_data(t1)
    args = SimpleNamespace(task_id="T1", result_json=json.dumps({"result_id": "r1"}), stage="EVIDENCE_READY")
    out = wq.cmd_complete(args, data, time.time())
    assert out["done"] == "T1"
    assert data["tasks"]["T1"]["status"] == "VERIFYING"


def test_complete_releases_lease():
    t1 = _task("T1", status="CLAIMED")
    data = _fresh_data(t1)
    data["leases"]["T1"] = {"worker": "w1", "write_scopes": [], "claimed_at": time.time()}
    args = SimpleNamespace(task_id="T1", result_json=json.dumps({"result_id": "r1"}), stage="ACCEPTED")
    wq.cmd_complete(args, data, time.time())
    assert "T1" not in data["leases"]


def test_complete_triggers_dependency_promotion():
    """Completing T1 in ACCEPTED stage should immediately activate T2."""
    t1 = _task("T1", status="CLAIMED")
    t2 = _task("T2", status="WAITING", deps=["T1"])
    data = _fresh_data(t1, t2)
    args = SimpleNamespace(task_id="T1", result_json=json.dumps({"result_id": "r1"}), stage="ACCEPTED")
    out = wq.cmd_complete(args, data, time.time())
    assert "T2" in out["newly_ready"]
    assert data["tasks"]["T2"]["status"] == "READY"


def test_complete_unknown_task_returns_error():
    data = _fresh_data()
    args = SimpleNamespace(task_id="X", result_json=json.dumps({"result_id": "r1"}), stage="ACCEPTED")
    out = wq.cmd_complete(args, data, time.time())
    assert "error" in out


# ─── cmd_block() ─────────────────────────────────────────────────────────────

def test_block_sets_status_and_reason():
    t1 = _task("T1", status="CLAIMED")
    data = _fresh_data(t1)
    data["leases"]["T1"] = {"worker": "w1", "write_scopes": [], "claimed_at": time.time()}
    args = SimpleNamespace(task_id="T1", reason="EXTERNAL_DEPENDENCY")
    out = wq.cmd_block(args, data, time.time())
    assert out["blocked"] == "T1"
    assert data["tasks"]["T1"]["status"] == "BLOCKED"
    assert data["tasks"]["T1"]["block_reason"] == "EXTERNAL_DEPENDENCY"
    assert "T1" not in data["leases"]  # lease released


def test_block_unknown_task_returns_error():
    data = _fresh_data()
    args = SimpleNamespace(task_id="GHOST", reason="X")
    out = wq.cmd_block(args, data, time.time())
    assert "error" in out


# ─── cmd_reconcile(): stale-lease recovery ───────────────────────────────────

def test_stale_lease_returns_task_to_ready():
    t1 = _task("T1", status="CLAIMED")
    data = _fresh_data(t1)
    old_time = time.time() - 7200  # 2 hours ago
    data["leases"]["T1"] = {"worker": "w1", "write_scopes": [], "claimed_at": old_time}
    args = SimpleNamespace(reclaim_stale=3600)
    out = wq.cmd_reconcile(args, data, time.time())
    assert "T1" in out["reclaimed"]
    assert data["tasks"]["T1"]["status"] == "READY"
    assert "T1" not in data["leases"]


def test_fresh_lease_is_not_reclaimed():
    t1 = _task("T1", status="CLAIMED")
    data = _fresh_data(t1)
    data["leases"]["T1"] = {"worker": "w1", "write_scopes": [], "claimed_at": time.time()}
    args = SimpleNamespace(reclaim_stale=3600)
    out = wq.cmd_reconcile(args, data, time.time())
    assert "T1" not in out["reclaimed"]
    assert data["tasks"]["T1"]["status"] == "CLAIMED"


def test_completed_task_not_reclaimed_even_if_stale():
    """A CLAIMED task that already has a result should not be reclaimed."""
    t1 = _task("T1", status="CLAIMED")
    t1["result"] = {"result_id": "r1"}
    data = _fresh_data(t1)
    old_time = time.time() - 7200
    data["leases"]["T1"] = {"worker": "w1", "write_scopes": [], "claimed_at": old_time}
    args = SimpleNamespace(reclaim_stale=3600)
    out = wq.cmd_reconcile(args, data, time.time())
    # The lease is cleaned up but the task status should NOT be reverted to READY
    assert "T1" not in out["reclaimed"]


# ─── live_scopes() ───────────────────────────────────────────────────────────

def test_live_scopes_excludes_stale_leases():
    data = {
        "leases": {
            "T1": {"write_scopes": ["scope/A"], "claimed_at": time.time() - 7200},
        }
    }
    held = wq.live_scopes(data, time.time(), stale_after=3600)
    assert "scope/A" not in held


def test_live_scopes_includes_fresh_leases():
    data = {
        "leases": {
            "T1": {"write_scopes": ["scope/B"], "claimed_at": time.time()},
        }
    }
    held = wq.live_scopes(data, time.time(), stale_after=3600)
    assert "scope/B" in held


# ─── cmd_add() validation ────────────────────────────────────────────────────

def test_add_missing_field_returns_error():
    data = _fresh_data()
    args = SimpleNamespace(json=json.dumps({"task_id": "T1"}))  # missing required fields
    out = wq.cmd_add(args, data)
    assert "error" in out
    assert "T1" not in data["tasks"]


def test_add_bad_status_returns_error():
    data = _fresh_data()
    task = _task("T1")
    task["status"] = "INVALID_STATUS"
    args = SimpleNamespace(json=json.dumps(task))
    out = wq.cmd_add(args, data)
    assert "error" in out


def test_add_valid_task_is_stored():
    data = _fresh_data()
    t = _task("T1", status="READY")
    args = SimpleNamespace(json=json.dumps(t))
    out = wq.cmd_add(args, data)
    assert out.get("added") == "T1"
    assert "T1" in data["tasks"]
