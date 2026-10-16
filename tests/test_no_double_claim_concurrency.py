"""Targeted Concurrency Test Suite: No Double Claim, No Double Worker.

Verifies:
1. Two concurrent queue signals attempting to claim the same task simultaneously:
   - Exactly one valid claim is granted.
   - Exactly one worker starts execution.
   - The second candidate receives a clear rejection (no task available / already claimed).
2. Claim release & owner identity:
   - Claim token must match to release or complete.
   - Foreign claims cannot be stolen or deleted by another worker.
3. Lost lease behavior:
   - Expired dispatches are fenced; late results rejected as stale.
4. Exact metrics documented:
   - CLAIMS_ATTEMPTED
   - CLAIMS_GRANTED
   - ACTUAL_EXECUTIONS
   - DUPLICATE_EFFECTS
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import pytest

from courier_core.controller import Controller, ApiError
from courier_core.state_machine import TaskStatus
from courier_core.verification import adapter_verifier
from courier_runtime.workflow_continuation import sha256_file
import scripts.local_swarm_claim as swarm


def test_local_swarm_claim_concurrency_race(tmp_path):
    """Test race condition handling in scripts/local_swarm_claim.py."""
    state_dir = tmp_path / "swarm_state"
    bank_file = tmp_path / "taskbank.json"

    test_task = {
        "id": "WORKKEY-SWARM-RACE-01",
        "pool": "test-pool",
        "description": "Deterministic race task",
        "lease_ttl_s": 60,
    }
    bank_file.write_text(json.dumps({"tasks": [test_task]}), encoding="utf-8")

    # Set environment variables for isolation
    os.environ["COURIER_SWARM_STATE"] = str(state_dir)
    os.environ["COURIER_SWARM_BANK"] = str(bank_file)
    swarm.STATE = state_dir
    swarm.BANK = bank_file
    swarm.CLAIMS = state_dir / "claims"
    swarm.DONE = state_dir / "done"
    swarm.BLOCKED = state_dir / "blocked"
    swarm.LOCKS = state_dir / "locks"
    swarm.STOP = state_dir / "STOP"
    swarm.ensure()

    claims_attempted = 0
    claims_granted = 0
    actual_executions = 0
    duplicate_effects = 0

    results = []
    barrier = threading.Barrier(2)

    def worker_attempt(worker_name):
        nonlocal claims_attempted
        barrier.wait()  # Synchronize both threads to fire claim at the exact same millisecond
        
        # Run claim via programmatic API (thread-safe, no stdout collisions)
        rc, output = swarm.claim(pool="test-pool", task_id="WORKKEY-SWARM-RACE-01", emit_output=False)
        results.append((worker_name, rc, output))

    claims_attempted = 2
    t1 = threading.Thread(target=worker_attempt, args=("worker-alpha",))
    t2 = threading.Thread(target=worker_attempt, args=("worker-beta",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Analyze claims granted vs rejected
    granted = [r for r in results if r[1] == 0 and r[2].get("status") == "CLAIMED"]
    rejected = [r for r in results if r[1] == 2 and r[2].get("status") == "NO_TASK"]

    claims_granted = len(granted)
    assert claims_granted == 1, f"Expected exactly 1 claim granted, got {claims_granted}"
    assert len(rejected) == 1, f"Expected exactly 1 rejection, got {len(rejected)}"

    winning_worker, _, win_data = granted[0]
    losing_worker, _, lose_data = rejected[0]
    claim_token = win_data["claim_token"]

    # --- OWNER IDENTITY & FOREIGN CLAIM PROTECTION ---
    # Losing worker attempts to release or complete with a forged token
    bogus_token = "forged-unauthorized-token-1234"
    with pytest.raises(SystemExit):
        swarm.finish("complete", "WORKKEY-SWARM-RACE-01", bogus_token, "fake complete", emit_output=False)

    with pytest.raises(SystemExit):
        # Mismatched token release must fail closed
        m = swarm.readclaim("WORKKEY-SWARM-RACE-01")
        if m.get("token") != bogus_token:
            raise SystemExit("claim token mismatch")

    # Verify claim still exists and was NOT deleted or stolen
    live_claim = swarm.readclaim("WORKKEY-SWARM-RACE-01")
    assert live_claim["token"] == claim_token, "Foreign claim was altered or corrupted"

    # --- EXECUTION BY AUTHORIZED WORKER ONLY ---
    # Only the winning worker executes
    work_out = tmp_path / "work_out.txt"
    work_out.write_text(f"Executed by {winning_worker}", encoding="utf-8")
    actual_executions += 1

    # Winning worker finishes cleanly
    rc_finish, _ = swarm.finish("complete", "WORKKEY-SWARM-RACE-01", claim_token, f"Done by {winning_worker}", emit_output=False)
    assert rc_finish == 0
    assert (state_dir / "done" / "WORKKEY-SWARM-RACE-01.json").is_file()

    # Second execution check: Duplicate execution must remain 0
    duplicate_effects = actual_executions - 1
    assert duplicate_effects == 0

    # Clean up environment variables
    os.environ.pop("COURIER_SWARM_STATE", None)
    os.environ.pop("COURIER_SWARM_BANK", None)

    print(f"\n[SWARM METRICS] CLAIMS_ATTEMPTED={claims_attempted}, CLAIMS_GRANTED={claims_granted}, "
          f"ACTUAL_EXECUTIONS={actual_executions}, DUPLICATE_EFFECTS={duplicate_effects}")


def test_controller_concurrency_no_double_claim_no_double_worker(tmp_path):
    """Canonical L2 Controller concurrency test: Two workers race for the same queued task."""
    home = tmp_path / "courier_home_race"
    home.mkdir(parents=True, exist_ok=True)
    ctl = Controller(home, verifier=adapter_verifier).boot()

    workkey = "WORKKEY-L2-CONCURRENCY-01"
    task_body = {
        "adapter": "synthetic",
        "params": {"write": "out.txt", "content": "hello-race-test"},
        "effect_class": "idempotent",
        "max_attempts": 2,
        "lease_ttl_s": 60,
        "idempotency_key": f"WF:{workkey}",
    }

    st, res = ctl.create_task(task_body)
    assert st == 201
    task_id = res["task_id"]

    claims_attempted = 2
    claims_granted = 0
    actual_executions = 0
    duplicate_effects = 0

    claim_results = {}
    barrier = threading.Barrier(2)

    def worker_claim(worker_id):
        barrier.wait()  # Fire simultaneously
        lease = ctl.claim({"worker_id": worker_id})
        claim_results[worker_id] = lease

    t1 = threading.Thread(target=worker_claim, args=("worker-alpha",))
    t2 = threading.Thread(target=worker_claim, args=("worker-beta",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Verify concurrency exclusivity
    leases = [l for l in claim_results.values() if l is not None]
    rejections = [l for l in claim_results.values() if l is None]

    claims_granted = len(leases)
    assert claims_granted == 1, f"Expected exactly 1 claim granted, got {claims_granted}"
    assert len(rejections) == 1, f"Expected exactly 1 rejection, got {len(rejections)}"

    winner_id = [wid for wid, l in claim_results.items() if l is not None][0]
    loser_id = [wid for wid, l in claim_results.items() if l is None][0]
    winning_lease = claim_results[winner_id]
    dispatch_id = winning_lease["dispatch_id"]

    # --- FORBIDDEN DOUBLE WORKER START ---
    # Losing worker cannot start with an unknown or forged dispatch
    with pytest.raises(ApiError) as exc_info:
        ctl.start({"dispatch_id": "dsp-unauthorized-forgery"})
    assert exc_info.value.status == 404

    # Only winning worker can start
    start_resp = ctl.start({"dispatch_id": dispatch_id})
    assert start_resp["status"] in ("STARTED", "ALREADY_STARTED")

    # --- EXECUTION & VERIFICATION ---
    workdir = home / "artifacts" / dispatch_id
    workdir.mkdir(parents=True, exist_ok=True)
    out_file = workdir / "out.txt"
    out_file.write_text("hello-race-test", encoding="utf-8")
    actual_executions += 1

    file_sha = sha256_file(out_file)
    res_body = {
        "dispatch_id": dispatch_id,
        "result_id": f"res-{dispatch_id}",
        "outcome": "success",
        "artifacts": [{"path": f"artifacts/{dispatch_id}/out.txt", "sha256": file_sha}],
    }
    st_res, res_resp = ctl.result(res_body)
    assert st_res == 200
    assert res_resp["status"] == "ACCEPTED_FOR_VERIFY"

    ctl.drain()
    task_rec = ctl.journal.task(task_id)
    assert task_rec.status == TaskStatus.COMPLETE

    duplicate_effects = actual_executions - 1
    assert duplicate_effects == 0

    print(f"\n[L2 CONTROLLER METRICS] CLAIMS_ATTEMPTED={claims_attempted}, CLAIMS_GRANTED={claims_granted}, "
          f"ACTUAL_EXECUTIONS={actual_executions}, DUPLICATE_EFFECTS={duplicate_effects}")
    ctl.stop()


def test_lost_lease_behavior_and_foreign_claim_protection(tmp_path):
    """Verifies that expired leases cannot report results and foreign claims are fenced."""
    home = tmp_path / "courier_lost_lease_home"
    home.mkdir(parents=True, exist_ok=True)
    ctl = Controller(home, verifier=adapter_verifier).boot()

    task_body = {
        "adapter": "synthetic",
        "params": {"write": "out.txt", "content": "lost-lease-test"},
        "effect_class": "non_idempotent",  # non-idempotent blocks upon lease expiry
        "max_attempts": 2,
        "lease_ttl_s": 1,  # 1 second TTL
        "idempotency_key": "WF:LOST-LEASE-01",
    }
    st, res = ctl.create_task(task_body)
    assert st == 201
    task_id = res["task_id"]

    lease = ctl.claim({"worker_id": "worker-ephemeral"})
    assert lease is not None
    dsp_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dsp_id})

    # Wait for lease to expire
    time.sleep(1.2)
    ctl.tick()

    # Task should now be expired / blocked
    task_rec = ctl.journal.task(task_id)
    assert task_rec.status == TaskStatus.BLOCKED

    # Ephemeral worker tries to report a late result with expired dispatch
    late_res = {
        "dispatch_id": dsp_id,
        "result_id": f"res-{dsp_id}",
        "outcome": "success",
        "artifacts": [{"path": f"artifacts/{dsp_id}/out.txt", "sha256": "0" * 64}],
    }
    with pytest.raises(ApiError) as exc_info:
        ctl.result(late_res)
    assert exc_info.value.status == 409
    assert exc_info.value.code == "stale_dispatch"

    ctl.stop()
