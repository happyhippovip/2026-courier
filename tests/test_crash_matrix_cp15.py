"""
tests/test_crash_matrix_cp15.py — Contract tests for CP-15 / CQ-15
Minimal Crash Matrix, Transition Cuts, and Data Loss Boundaries

Invariants:
1. Every relevant persistent transition cut has a deterministic expected recovery state.
2. Zero data loss on committed state across all crash boundaries.
3. Pre-persistence failure fails cleanly without state corruption; client retries idempotently.
4. Mid-execution worker loss quarantines non-idempotent uncertain effects without blind retry.
5. Outbox fsync before ACK ensures zero loss of completed execution results.
6. Verified results are immutable and preserved across restart ("Bestätigte Ergebnisse bleiben erhalten").
7. Redundant test cases reuse canonical verification fixtures; physical evidence is strictly isolated.
"""

import copy
import json
import uuid
import pytest
from pathlib import Path

from courier_core.crash_matrix import (
    CrashMatrix,
    CrashMatrixEntry,
    RecoveryExpectation,
    TransitionCut,
)
from courier_core.outbox_ack_boundary import (
    DurableOutboxBoundary,
    ResultIngestBoundary,
    ResultIngestStatus,
)
from server import app as server_app


@pytest.fixture
def http(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client()


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


def test_crash_matrix_canonical_transition_map_metadata():
    """Validates complete coverage of all 7 transition cuts in the machine-readable matrix."""
    tmap = CrashMatrix.transition_map()
    assert tmap["total_cuts"] == 7
    assert len(tmap["cuts"]) == 7

    cut_names = [c["cut"] for c in tmap["cuts"]]
    for cut in TransitionCut:
        assert cut.value in cut_names


def test_crash_matrix_cut1_pre_persistence_fails_cleanly_without_corrupt_state(http):
    """Cut 1: Pre-persistence failure (bad payload, client disconnect) writes zero partial state."""
    # Attempting to post invalid/truncated JSON
    res = http.post("/goals", headers=auth(), data="{'invalid_json': ", content_type="application/json")
    assert res.status_code == 400

    # Ensure state file contains no half-written or corrupted goals
    state = server_app.load_state()
    assert state.get("goals") == {}
    assert state.get("tasks") == {}


def test_crash_matrix_cut2_persisted_pre_claim_survives_crash_as_queued(http, tmp_path):
    """Cut 2: Task persisted to disk survives coordinator cold crash and is computed ready."""
    # 1. Post a valid goal with 1 step
    res = http.post("/goals", headers=auth(), json={
        "goal_text": "Cut 2 test",
        "workflow_plan": [{"task_id": "cut2-task-1", "target_agent": "mac", "artifacts": ["out2.txt"]}]
    })
    assert res.status_code == 200

    # 2. Simulate cold restart of coordinator
    state_file = tmp_path / "state.json"
    assert state_file.is_file()

    # Restart coordinator and run startup recovery
    from courier_core.startup_recovery import StartupRecoveryEngine
    engine = StartupRecoveryEngine()
    state = server_app.load_state()
    reconciled_state, report = engine.execute_recovery(state)

    # Task survived as QUEUED and is ready for dispatch
    task = reconciled_state["tasks"]["cut2-task-1"]
    assert task["status"] == "QUEUED"
    assert report.phase.value == "DISPATCH_READY"
    assert "cut2-task-1" in report.ready_task_ids


def test_crash_matrix_cut3_claimed_pre_start_quarantines_ambiguous_non_idempotent(http):
    """Cut 3: Claimed/Dispatched task whose worker vanishes without confirmed start is quarantined."""
    # Register worker & post non-idempotent task
    http.post("/workers/register", headers=auth(), json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]})
    http.post("/goals", headers=auth(), json={
        "goal_text": "Cut 3 non-idempotent",
        "workflow_plan": [{
            "task_id": "cut3-task-1",
            "target_agent": "mac",
            "artifacts": ["out3.txt"],
            "effect_class": "non_idempotent"
        }]
    })

    # Claim task -> status becomes DISPATCHED
    claimed = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()["task"]
    assert claimed["status"] == "DISPATCHED"

    # Simulate worker crash and stale expiry: advance worker's last_seen far into past
    state = server_app.load_state()
    state["workers"]["MAC-01"]["last_seen"] = 0
    server_app.save_state(state)

    # Trigger reclaim
    res = http.post("/tasks/reclaim_stale", headers=auth())
    assert res.status_code == 200

    # Invariant: Fehlende Runtime-Evidenz wird nicht erfunden!
    # Task must transition to HUMAN_REQUIRED / BLOCKED, NOT blindly retried!
    state = server_app.load_state()
    task = state["tasks"]["cut3-task-1"]
    assert task["status"] == "HUMAN_REQUIRED"
    assert task["recovery_reason"] == "STALE_WORKER_EFFECT_AMBIGUOUS"


def test_crash_matrix_cut4_running_mid_execution_fences_stale_zombie_worker(http):
    """Cut 4: Worker crashes mid-run; failover advances fencing token; zombie worker write is rejected."""
    # Register worker & claim task
    http.post("/workers/register", headers=auth(), json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]})
    res_goal = http.post("/goals", headers=auth(), json={
        "goal_text": "Cut 4 fencing test",
        "workflow_plan": [{"task_id": "cut4-task-1", "target_agent": "mac", "artifacts": ["out4.txt"]}]
    }).get_json()
    goal_id = res_goal["goal_id"]

    claimed = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()["task"]
    task_id = claimed["task_id"]
    dispatch_id = claimed["dispatch_id"]
    attempt_id = claimed["attempt_id"]
    old_fencing_token = claimed.get("fencing_token", 1)

    # Advance fencing token on server (simulating failover takeover by coordinator)
    state = server_app.load_state()
    state["tasks"][task_id]["fencing_token"] = old_fencing_token + 1
    server_app.save_state(state)

    # Zombie worker comes back from network partition and tries to submit result with old fencing token
    res = http.post("/tasks/result", headers=auth(), json={
        "goal_id": goal_id,
        "task_id": task_id,
        "worker_id": "MAC-01",
        "dispatch_id": dispatch_id,
        "attempt_id": attempt_id,
        "run_id": "run-cut4",
        "result_id": "res-cut4",
        "source_sha": "a" * 40,
        "status": "SUCCESS",
        "fencing_token": old_fencing_token,  # STALE!
        "artifacts": [{"path": "out4.txt", "sha256": "b" * 64, "size": 10}]
    })
    assert res.status_code == 409
    assert "stale fencing token" in res.get_json()["error"]


def test_crash_matrix_cut5_result_fsync_pre_ack_replays_from_outbox_without_side_effects(tmp_path):
    """Cut 5: Result fsynced to outbox before crash survives network drop; replay succeeds idempotently."""
    home = tmp_path / "worker_home"

    result_payload = {
        "task_id": "cut5-task-1",
        "attempt_id": 1,
        "dispatch_id": "dsp-cut5",
        "result_id": "res-cut5",
        "outcome": "SUCCESS",
        "artifacts": ["out5.txt"],
    }

    # Step 1: Worker writes result to outbox with fsync
    outbox_file = DurableOutboxBoundary.persist_result(home, result_payload)
    assert outbox_file.is_file()

    # Step 2: Simulate crash/drop before ACK: file is preserved
    assert outbox_file.exists()

    # Step 3: Replay to server (First delivery)
    task_state = {
        "task_id": "cut5-task-1",
        "attempt_id": 1,
        "dispatch_id": "dsp-cut5",
        "status": "DISPATCHED",
        "result": None,
    }
    outcome = ResultIngestBoundary.ingest_result(task_state, result_payload)
    assert outcome.status == ResultIngestStatus.ACK_RESULT_RECEIVED
    assert outcome.logical_effect_applied is True

    # Step 4: Outbox acknowledges and unlinks
    receipt = DurableOutboxBoundary.deliver_with_ack(home, "dsp-cut5", lambda p: {"status": "ACK_RESULT_RECEIVED"})
    assert receipt.cleared_from_outbox is True
    assert not outbox_file.exists()

    # Step 5: State holds result; duplicate delivery produces ZERO new logical mutations
    task_state["status"] = "RESULT_RECEIVED"
    task_state["result"] = result_payload

    dup_outcome = ResultIngestBoundary.ingest_result(task_state, result_payload)
    assert dup_outcome.status == ResultIngestStatus.ACK_DUPLICATE
    assert dup_outcome.logical_effect_applied is False


def test_crash_matrix_cut6_result_received_pre_verify_recovers_pending_verification(http):
    """Cut 6: Ingested result survives crash and is re-queued for verification without re-running code."""
    # Register, claim and submit result
    http.post("/workers/register", headers=auth(), json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]})
    res_goal = http.post("/goals", headers=auth(), json={
        "goal_text": "Cut 6 verify test",
        "workflow_plan": [{"task_id": "cut6-task-1", "target_agent": "mac", "artifacts": ["out6.txt"]}]
    }).get_json()
    goal_id = res_goal["goal_id"]

    claimed = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()["task"]
    task_id = claimed["task_id"]

    res = http.post("/tasks/result", headers=auth(), json={
        "goal_id": goal_id,
        "task_id": task_id,
        "worker_id": "MAC-01",
        "dispatch_id": claimed["dispatch_id"],
        "attempt_id": claimed["attempt_id"],
        "run_id": "run-cut6",
        "result_id": "res-cut6",
        "source_sha": "a" * 40,
        "status": "SUCCESS",
        "artifacts": [{"path": "out6.txt", "sha256": "b" * 64, "size": 10}]
    })
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # Verifier daemon crashes before signing receipt.
    # On recovery, pending verification endpoint returns the unverified result
    res_pending = http.get("/tasks/pending_verification", headers=verifier_auth())
    assert res_pending.status_code == 200
    pending_tasks = res_pending.get_json().get("tasks", [])
    assert any(t["task_id"] == "cut6-task-1" for t in pending_tasks)


def test_crash_matrix_cut7_verified_pre_handoff_preserves_confirmed_result_and_advances_dag(http):
    """Cut 7: Verified result remains confirmed across crash; DAG resolver advances to next step."""
    # Setup 2-step workflow: step 1 -> step 2
    http.post("/workers/register", headers=auth(), json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]})
    res_goal = http.post("/goals", headers=auth(), json={
        "goal_text": "Cut 7 2-step DAG",
        "workflow_plan": [
            {"task_id": "step-1", "target_agent": "mac", "artifacts": ["out1.txt"]},
            {"task_id": "step-2", "target_agent": "mac", "artifacts": ["out2.txt"]}
        ]
    }).get_json()
    goal_id = res_goal["goal_id"]

    # Step 1: Claim and submit result
    claim1 = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()["task"]
    res_post = http.post("/tasks/result", headers=auth(), json={
        "goal_id": goal_id,
        "task_id": "step-1",
        "worker_id": "MAC-01",
        "dispatch_id": claim1["dispatch_id"],
        "attempt_id": claim1["attempt_id"],
        "run_id": "run-step1",
        "result_id": "res-step1",
        "source_sha": "a" * 40,
        "status": "SUCCESS",
        "artifacts": [{"path": "out1.txt", "sha256": "b" * 64, "size": 10}]
    })
    assert res_post.status_code == 200, res_post.get_json()

    # Verifier verifies step 1
    verify_res = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": "step-1",
        "verifier_id": "V-INDEPENDENT-01",
        "result_id": "res-step1",
        "artifacts": [{"path": "out1.txt", "sha256": "b" * 64, "size": 10}],
        "verdict": "PASS"
    })
    assert verify_res.status_code == 200, verify_res.get_json()

    # Coordinator crashes and re-boots
    from courier_core.startup_recovery import StartupRecoveryEngine
    engine = StartupRecoveryEngine()
    state = server_app.load_state()
    reconciled_state, report = engine.execute_recovery(state)

    # Invariant: Bestätigte Ergebnisse bleiben erhalten!
    # Step 1 stays RECONCILED / verified; step 2 is ready for claim
    assert reconciled_state["tasks"]["step-1"]["status"] == "RECONCILED"
    assert "step-2" in report.ready_task_ids
