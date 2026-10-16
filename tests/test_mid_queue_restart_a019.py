"""Test Suite for A019: Mid Queue Restart Recovery.

Verifies:
1. Deterministic three-task workflow A -> B -> C:
   - Stage A: Data producer (produces raw test data).
   - Stage B: Data processor (consumes A's data and computes aggregates).
   - Stage C: Invariant validator (validates B's aggregates against ground truth).
2. Controlled test controller restart after confirmed A and before completion of B:
   - A remains DONE (TaskStatus.COMPLETE preserved in SQLite journal).
   - In-flight/unconfirmed B is NOT blindly double-started (another worker claim returns None; lease restored with restart_grace).
   - Stage C is forbidden/blocked until B yields a valid accepted result.
   - A confirmed B is preserved across subsequent restarts.
3. Execution metrics:
   - Exactly 1 execution per stage (Total executions = 3).
   - Zero model calls (MODEL_CALLS = 0, spend €0.00).
   - Human-Relay-Count strictly 0.
"""

import json
from pathlib import Path
import pytest

from courier_core.controller import Controller
from courier_core.state_machine import TaskStatus
from courier_runtime.workflow_continuation import (
    WorkflowAdmissionPacket,
    WorkflowContinuationEngine,
    WorkflowStage,
    sha256_file,
    workflow_stage_verifier,
)


def _make_controller(home: Path) -> Controller:
    """Boots Controller with workflow stage verifier."""
    def verifier_factory(adapter_name: str):
        return workflow_stage_verifier

    return Controller(home, verifier=verifier_factory).boot()


def test_mid_queue_restart_a019_e2e(tmp_path):
    """A019: Controlled test controller restart after confirmed A and before completion of B."""
    home = tmp_path / "courier_mid_restart_home"
    home.mkdir(parents=True, exist_ok=True)

    workkey_a = "A019-STAGE-A-PRODUCE"
    workkey_b = "A019-STAGE-B-PROCESS"
    workkey_c = "A019-STAGE-C-VALIDATE"

    stages = [
        WorkflowStage(workkey=workkey_a, stage_id="A", action="produce", adapter="synthetic"),
        WorkflowStage(workkey=workkey_b, stage_id="B", action="process", adapter="synthetic", depends_on=[workkey_a]),
        WorkflowStage(workkey=workkey_c, stage_id="C", action="validate", adapter="synthetic", depends_on=[workkey_b]),
    ]
    packet = WorkflowAdmissionPacket(workflow_id="WF-A019-MID-RESTART", stages=stages)

    # -------------------------------------------------------------------------
    # PHASE 1: Boot Controller 1, Execute Stage A to COMPLETE
    # -------------------------------------------------------------------------
    ctl1 = _make_controller(home)
    worker_b_id = "surrogate-worker-b-primary"

    # 1. Admit Stage A
    task_body_a = {
        "adapter": "synthetic",
        "params": {
            "stage": "A",
            "action": "produce",
            "workkey": workkey_a,
            "workflow_id": packet.workflow_id,
            "raw_numbers": [10, 20, 30, 40],
        },
        "effect_class": "idempotent",
        "max_attempts": 2,
        "lease_ttl_s": 60,
        "idempotency_key": f"{packet.workflow_id}:{workkey_a}",
    }
    st_a, res_a = ctl1.create_task(task_body_a)
    assert st_a == 201
    task_id_a = res_a["task_id"]

    lease_a = ctl1.claim({"worker_id": "worker-a"})
    assert lease_a is not None and lease_a["task_id"] == task_id_a
    dispatch_id_a = lease_a["dispatch_id"]
    ctl1.start({"dispatch_id": dispatch_id_a})

    # Produce A's artifact
    workdir_a = home / "artifacts" / dispatch_id_a
    workdir_a.mkdir(parents=True, exist_ok=True)
    file_a = workdir_a / "data_a.json"
    file_a.write_text(json.dumps({
        "stage": "A",
        "workkey": workkey_a,
        "raw_numbers": [10, 20, 30, 40],
        "count": 4,
    }), encoding="utf-8")
    sha_a = sha256_file(file_a)

    res_st_a, res_b_a = ctl1.result({
        "dispatch_id": dispatch_id_a,
        "result_id": f"res-{dispatch_id_a}",
        "outcome": "success",
        "artifacts": [{"path": f"artifacts/{dispatch_id_a}/data_a.json", "sha256": sha_a}],
    })
    assert res_st_a == 200
    ctl1.drain()

    # Stage A is confirmed DONE
    rec_a_before = ctl1.journal.task(task_id_a)
    assert rec_a_before.status == TaskStatus.COMPLETE, "Stage A must be COMPLETE before B starts"

    # -------------------------------------------------------------------------
    # PHASE 2: Start Stage B on ctl1 (Vor Abschluss von B)
    # -------------------------------------------------------------------------
    rel_path_a = f"artifacts/{dispatch_id_a}/data_a.json"
    task_body_b = {
        "adapter": "synthetic",
        "params": {
            "stage": "B",
            "action": "process",
            "workkey": workkey_b,
            "workflow_id": packet.workflow_id,
            "input_artifact": rel_path_a,
        },
        "effect_class": "idempotent",
        "max_attempts": 2,
        "lease_ttl_s": 60,
        "idempotency_key": f"{packet.workflow_id}:{workkey_b}",
    }
    st_b, res_b = ctl1.create_task(task_body_b)
    assert st_b == 201
    task_id_b = res_b["task_id"]

    lease_b = ctl1.claim({"worker_id": worker_b_id})
    assert lease_b is not None and lease_b["task_id"] == task_id_b
    dispatch_id_b = lease_b["dispatch_id"]
    ctl1.start({"dispatch_id": dispatch_id_b})

    # Vor Abschluss von B: Task B is RUNNING, unconfirmed
    rec_b_before = ctl1.journal.task(task_id_b)
    assert rec_b_before.status == TaskStatus.RUNNING, "Stage B must be RUNNING (unconfirmed)"
    assert rec_b_before.dispatch_id == dispatch_id_b

    # Vorher-Zustand snapshot
    vorher_status = {
        "stage_a": rec_a_before.status.value,
        "stage_b": rec_b_before.status.value,
        "stage_c": "NOT_STARTED",
    }
    assert vorher_status == {"stage_a": "COMPLETE", "stage_b": "RUNNING", "stage_c": "NOT_STARTED"}

    # -------------------------------------------------------------------------
    # PHASE 3: Kontrollierter Testcontroller-Neustart (ctl1 -> ctl2)
    # -------------------------------------------------------------------------
    ctl1.stop()
    ctl2 = _make_controller(home)

    # CHECK 1: A bleibt DONE
    rec_a_after1 = ctl2.journal.task(task_id_a)
    assert rec_a_after1.status == TaskStatus.COMPLETE, "CHECK 1 FAILED: A must remain COMPLETE after restart"

    # CHECK 2: Ein unklar laufendes B wird nicht blind doppelt gestartet
    rec_b_after1 = ctl2.journal.task(task_id_b)
    assert rec_b_after1.status == TaskStatus.RUNNING, "Task B must remain RUNNING with restored active lease"
    assert rec_b_after1.dispatch_id == dispatch_id_b

    # A different worker attempts to claim from ctl2
    duplicate_claim = ctl2.claim({"worker_id": "unauthorized-double-starter"})
    assert duplicate_claim is None, "CHECK 2 FAILED: Task B was blindly double-started to another worker!"

    # CHECK 3: C wird erst nach gültigem B-Resultat erlaubt
    engine_temp = WorkflowContinuationEngine(controller=ctl2, home=home)
    recovered_map = engine_temp.recover_from_ledger(packet)
    assert recovered_map[workkey_a] == "COMPLETE"
    assert recovered_map[workkey_b] == "RUNNING"
    assert workkey_b not in engine_temp.completed_stages

    # Attempting to run Stage C while B is unconfirmed must fail closed
    with pytest.raises(RuntimeError, match=f"CANNOT_CONTINUE: Dependency '{workkey_b}' is not completed"):
        engine_temp.admit_and_run(WorkflowAdmissionPacket(
            workflow_id=packet.workflow_id,
            stages=[stages[2]],  # Stage C only
        ))

    # -------------------------------------------------------------------------
    # PHASE 4: Worker B delivers result to ctl2, B is verified and reaches COMPLETE
    # -------------------------------------------------------------------------
    workdir_b = home / "artifacts" / dispatch_id_b
    workdir_b.mkdir(parents=True, exist_ok=True)
    file_b = workdir_b / "data_b.json"
    file_b.write_text(json.dumps({
        "stage": "B",
        "workkey": workkey_b,
        "source_workkey": workkey_a,
        "sum": 100,
        "mean": 25.0,
        "count": 4,
        "min": 10,
        "max": 40,
    }), encoding="utf-8")
    sha_b = sha256_file(file_b)

    res_st_b, res_b_resp = ctl2.result({
        "dispatch_id": dispatch_id_b,
        "result_id": f"res-{dispatch_id_b}",
        "outcome": "success",
        "artifacts": [{"path": f"artifacts/{dispatch_id_b}/data_b.json", "sha256": sha_b}],
    })
    assert res_st_b == 200
    assert res_b_resp["status"] == "ACCEPTED_FOR_VERIFY"
    ctl2.drain()

    rec_b_verified = ctl2.journal.task(task_id_b)
    assert rec_b_verified.status == TaskStatus.COMPLETE, "Stage B must be COMPLETE after verification"

    # -------------------------------------------------------------------------
    # PHASE 5: Zweiter Kontrollierter Neustart (ctl2 -> ctl3)
    # CHECK 4: Ein bestätigtes B bleibt erhalten
    # -------------------------------------------------------------------------
    ctl2.stop()
    ctl3 = _make_controller(home)

    rec_a_after2 = ctl3.journal.task(task_id_a)
    rec_b_after2 = ctl3.journal.task(task_id_b)
    assert rec_a_after2.status == TaskStatus.COMPLETE, "A must remain COMPLETE after second restart"
    assert rec_b_after2.status == TaskStatus.COMPLETE, "CHECK 4 FAILED: Confirmed B must remain COMPLETE after restart"

    # -------------------------------------------------------------------------
    # PHASE 6: Stage C wird nach gültigem B-Resultat erlaubt und ausgeführt
    # -------------------------------------------------------------------------
    engine_final = WorkflowContinuationEngine(controller=ctl3, home=home, worker_id="surrogate-worker-c")
    manifest = engine_final.admit_and_run(packet)

    # Assert final completion of the entire 3-task workflow
    assert manifest["status"] == "COMPLETED"
    assert manifest["stages_completed"] == [workkey_a, workkey_b, workkey_c]

    # Check Nachher-Zustand
    nachher_status = {
        "stage_a": ctl3.journal.task(task_id_a).status.value,
        "stage_b": ctl3.journal.task(task_id_b).status.value,
        "stage_c": ctl3.journal.task(manifest["completed_stages"][workkey_c]["task_id"]).status.value,
    }
    assert nachher_status == {"stage_a": "COMPLETE", "stage_b": "COMPLETE", "stage_c": "COMPLETE"}

    # Ausführungszahlen
    assert manifest["execution_counts"][workkey_a] == 1
    assert manifest["execution_counts"][workkey_b] == 1
    assert manifest["execution_counts"][workkey_c] == 1
    assert manifest["total_local_executions"] == 3
    assert manifest["model_calls"] == 0
    assert manifest["human_relay_count"] == 0

    # Chain verification on disk ledger
    assert ctl3.journal.verify_chain().ok is True

    ctl3.stop()
