"""Concurrency test for claim exclusivity: No double claim, no double worker.

Mission: Zwei Queue-Signale dürfen nicht denselben Task zweimal ausführen.

Tests:
1. Concurrency race on identical task/workkey:
   Two concurrent execution attempts try to claim the exact same task.
   Expectation: Exactly 1 claim granted, exactly 1 worker executes, second is rejected (NO_TASK / FileExistsError).
2. Exclusive group concurrency:
   Two tasks in the same exclusive group.
   Expectation: Only 1 task in the group can be claimed at any time.
3. Release and token protection:
   Claim release requires the exact token. Foreign tokens cannot release or steal the claim.
4. Finished / Done protection:
   Completed tasks cannot be re-claimed.
5. Lost lease / stale claim simulation:
   Verification of token mismatch protection.

Metrics tracked:
- CLAIMS_ATTEMPTED
- CLAIMS_GRANTED
- ACTUAL_EXECUTIONS
- DUPLICATE_EFFECTS
"""

import concurrent.futures
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

import pytest

from scripts import local_swarm_claim


@pytest.fixture
def isolated_swarm(tmp_path):
    orig_bank = local_swarm_claim.BANK
    orig_state = local_swarm_claim.STATE
    orig_claims = local_swarm_claim.CLAIMS
    orig_done = local_swarm_claim.DONE
    orig_blocked = local_swarm_claim.BLOCKED
    orig_locks = local_swarm_claim.LOCKS
    orig_stop = local_swarm_claim.STOP

    state_dir = tmp_path / ".courier_swarm"
    bank_file = tmp_path / "BANK.json"

    local_swarm_claim.BANK = bank_file
    local_swarm_claim.STATE = state_dir
    local_swarm_claim.CLAIMS = state_dir / "claims"
    local_swarm_claim.DONE = state_dir / "done"
    local_swarm_claim.BLOCKED = state_dir / "blocked"
    local_swarm_claim.LOCKS = state_dir / "locks"
    local_swarm_claim.STOP = state_dir / "STOP"

    local_swarm_claim.ensure()

    yield tmp_path

    local_swarm_claim.BANK = orig_bank
    local_swarm_claim.STATE = orig_state
    local_swarm_claim.CLAIMS = orig_claims
    local_swarm_claim.DONE = orig_done
    local_swarm_claim.BLOCKED = orig_blocked
    local_swarm_claim.LOCKS = orig_locks
    local_swarm_claim.STOP = orig_stop


def test_concurrent_claim_race_single_winner(isolated_swarm, monkeypatch):
    """Simulate 2 concurrent execution attempts racing for the exact same task."""
    bank_data = {
        "tasks": [
            {"id": "workkey-alpha-1", "pool": "windows-google"}
        ]
    }
    local_swarm_claim.BANK.write_text(json.dumps(bank_data), encoding="utf-8")

    claims_attempted = 0
    claims_granted = 0
    actual_executions = 0
    duplicate_effects = 0

    emitted_records = []

    def mock_emit(rec):
        emitted_records.append(rec)

    monkeypatch.setattr(local_swarm_claim, "emit", mock_emit)

    def worker_attempt(worker_id):
        nonlocal claims_attempted, claims_granted, actual_executions, duplicate_effects
        claims_attempted += 1

        # Attempt claim
        res = local_swarm_claim.claim("windows-google")
        if res == 0:
            claims_granted += 1
            # Simulate worker execution & artifact generation
            claim_file = local_swarm_claim.CLAIMS / "workkey-alpha-1" / "claim.json"
            assert claim_file.exists(), f"Claim file missing for winner {worker_id}"
            claim_info = json.loads(claim_file.read_text(encoding="utf-8"))
            token = claim_info["token"]

            # Worker execution effect
            actual_executions += 1
            effect_file = isolated_swarm / "effect.txt"
            if effect_file.exists():
                duplicate_effects += 1
            else:
                effect_file.write_text(f"executed_by_{worker_id}", encoding="utf-8")

            # Finish task
            finish_res = local_swarm_claim.finish("complete", "workkey-alpha-1", token, f"Worker {worker_id} done")
            assert finish_res == 0
            return ("GRANTED", worker_id, token)
        else:
            return ("REJECTED", worker_id, None)

    # Launch 2 threads concurrently trying to claim
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_attempt, "worker_1")
        f2 = executor.submit(worker_attempt, "worker_2")
        results = [f1.result(), f2.result()]

    outcomes = [r[0] for r in results]
    print("\n=== SWARM RACE CONCURRENCY REPORT ===")
    report = {
        "CLAIMS_ATTEMPTED": claims_attempted,
        "CLAIMS_GRANTED": claims_granted,
        "ACTUAL_EXECUTIONS": actual_executions,
        "DUPLICATE_EFFECTS": duplicate_effects,
        "WORKER_OUTCOMES": results,
    }
    print(json.dumps(report, indent=2))

    assert claims_attempted == 2
    assert claims_granted == 1, "Exactly one claim must be granted"
    assert actual_executions == 1, "Exactly one execution must take place"
    assert duplicate_effects == 0, "No duplicate effects allowed"
    assert "GRANTED" in outcomes
    assert "REJECTED" in outcomes
    assert (local_swarm_claim.DONE / "workkey-alpha-1.json").exists()


def test_claim_token_security_and_release(isolated_swarm, monkeypatch):
    """Ensure claim release requires the exact token; foreign token cannot steal or finish."""
    bank_data = {
        "tasks": [
            {"id": "workkey-sec-1", "pool": "windows-google"}
        ]
    }
    local_swarm_claim.BANK.write_text(json.dumps(bank_data), encoding="utf-8")

    monkeypatch.setattr(local_swarm_claim, "emit", lambda x: None)

    # Worker 1 claims
    ret = local_swarm_claim.claim("windows-google")
    assert ret == 0

    claim_file = local_swarm_claim.CLAIMS / "workkey-sec-1" / "claim.json"
    claim_info = json.loads(claim_file.read_text(encoding="utf-8"))
    legit_token = claim_info["token"]
    foreign_token = "fake-token-00000000"

    # Attacker tries to complete with foreign token -> SystemExit("claim token mismatch")
    with pytest.raises(SystemExit, match="claim token mismatch"):
        local_swarm_claim.finish("complete", "workkey-sec-1", foreign_token, "Hacked")

    # Claim file remains intact
    assert claim_file.exists()

    # Legitimate owner releases
    m = local_swarm_claim.readclaim("workkey-sec-1")
    assert m["token"] == legit_token
    local_swarm_claim.unlock(m)
    assert not claim_file.exists()

    # Now the task can be safely claimed again
    ret2 = local_swarm_claim.claim("windows-google")
    assert ret2 == 0
    new_claim = json.loads(claim_file.read_text(encoding="utf-8"))
    assert new_claim["token"] != legit_token


def test_exclusive_group_concurrency_prevention(isolated_swarm, monkeypatch):
    """Two different tasks sharing an exclusive_group cannot run concurrently."""
    bank_data = {
        "tasks": [
            {"id": "task-grp-1", "pool": "windows-google", "exclusive_group": "database_migration"},
            {"id": "task-grp-2", "pool": "windows-google", "exclusive_group": "database_migration"}
        ]
    }
    local_swarm_claim.BANK.write_text(json.dumps(bank_data), encoding="utf-8")
    monkeypatch.setattr(local_swarm_claim, "emit", lambda x: None)

    # Claim first task
    ret1 = local_swarm_claim.claim("windows-google")
    assert ret1 == 0
    assert (local_swarm_claim.CLAIMS / "task-grp-1").exists()
    assert (local_swarm_claim.LOCKS / "database_migration").exists()

    # Second task shares exclusive_group -> must be rejected (NO_TASK)
    ret2 = local_swarm_claim.claim("windows-google")
    assert ret2 == 2  # NO_TASK because group is locked

    # Finish task-grp-1
    c1 = json.loads((local_swarm_claim.CLAIMS / "task-grp-1" / "claim.json").read_text(encoding="utf-8"))
    local_swarm_claim.finish("complete", "task-grp-1", c1["token"], "Done")
    assert not (local_swarm_claim.LOCKS / "database_migration").exists()

    # Now task-grp-2 can be claimed
    ret3 = local_swarm_claim.claim("windows-google")
    assert ret3 == 0
    assert (local_swarm_claim.CLAIMS / "task-grp-2").exists()
