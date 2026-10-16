"""Test Suite for A018: Three Unique Task Continuation.

Verifies:
1. Three unique deterministic tasks A, B, and C:
   - Task A produces test data.
   - Task B consumes and processes A's data.
   - Task C validates B's processed result against ground truth.
2. Single workflow admission drives A -> B -> C continuation to completion.
3. Actual physical state and process evidence:
   - Real files on disk with SHA256 integrity.
   - Persistent SQLite ledger events for all 3 tasks in courier.db.
   - Chain verification and cold replay preservation.
4. Execution metrics:
   - Three distinct workkeys.
   - Exactly 1 local execution per task (total 3 executions).
   - Zero model calls (MODEL_CALLS=0, spend €0.00).
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


def _make_controller_with_verifier(home: Path) -> Controller:
    """Boots Controller with the workflow stage verifier."""
    def verifier_factory(adapter_name: str):
        return workflow_stage_verifier

    return Controller(home, verifier=verifier_factory).boot()


def test_three_unique_task_continuation_e2e(tmp_path):
    """A018: Full physical end-to-end continuation A -> B -> C."""
    home = tmp_path / "courier_home"
    home.mkdir(parents=True, exist_ok=True)

    ctl = _make_controller_with_verifier(home)

    # 1. Three distinct workkeys
    workkey_a = "A018-STAGE-A-PRODUCE"
    workkey_b = "A018-STAGE-B-PROCESS"
    workkey_c = "A018-STAGE-C-VALIDATE"

    stages = [
        WorkflowStage(workkey=workkey_a, stage_id="A", action="produce", adapter="synthetic"),
        WorkflowStage(workkey=workkey_b, stage_id="B", action="process", adapter="synthetic", depends_on=[workkey_a]),
        WorkflowStage(workkey=workkey_c, stage_id="C", action="validate", adapter="synthetic", depends_on=[workkey_b]),
    ]

    packet = WorkflowAdmissionPacket(workflow_id="WF-A018-TRIPLET", stages=stages)

    # 2. Run engine over Controller
    engine = WorkflowContinuationEngine(controller=ctl, home=home, worker_id="surrogate-worker-a018")
    manifest = engine.admit_and_run(packet)

    # --- VERIFICATION OF DELIVERABLES ---
    # Deliverable 1: Three different workkeys
    assert manifest["workkeys"]["A"] == workkey_a
    assert manifest["workkeys"]["B"] == workkey_b
    assert manifest["workkeys"]["C"] == workkey_c
    assert len({workkey_a, workkey_b, workkey_c}) == 3

    # Deliverable 2: Real local execution metrics
    assert manifest["status"] == "COMPLETED"
    assert manifest["execution_counts"][workkey_a] == 1
    assert manifest["execution_counts"][workkey_b] == 1
    assert manifest["execution_counts"][workkey_c] == 1
    assert manifest["total_local_executions"] == 3
    assert manifest["model_calls"] == 0

    # Deliverable 3: Human-Relay-Count
    assert manifest["human_relay_count"] == 0

    # --- PHYSICAL STATE AND PROCESS EVIDENCE ---
    # Evidence 1: Physical disk artifacts
    stage_a_rec = manifest["completed_stages"][workkey_a]
    stage_b_rec = manifest["completed_stages"][workkey_b]
    stage_c_rec = manifest["completed_stages"][workkey_c]

    file_a = home / stage_a_rec["artifact_rel_path"]
    file_b = home / stage_b_rec["artifact_rel_path"]
    file_c = home / stage_c_rec["artifact_rel_path"]

    assert file_a.is_file(), "Stage A artifact missing on disk"
    assert file_b.is_file(), "Stage B artifact missing on disk"
    assert file_c.is_file(), "Stage C artifact missing on disk"

    # Verify content progression:
    # A produced [10, 20, 30, 40]
    data_a = json.loads(file_a.read_text(encoding="utf-8"))
    assert data_a["raw_numbers"] == [10, 20, 30, 40]
    assert sha256_file(file_a) == stage_a_rec["artifact_sha"]

    # B processed A's data: sum=100, mean=25.0, count=4
    data_b = json.loads(file_b.read_text(encoding="utf-8"))
    assert data_b["source_workkey"] == workkey_a
    assert data_b["sum"] == 100
    assert data_b["mean"] == 25.0
    assert data_b["count"] == 4
    assert sha256_file(file_b) == stage_b_rec["artifact_sha"]

    # C validated B's result: ground truth verified
    data_c = json.loads(file_c.read_text(encoding="utf-8"))
    assert data_c["validated_workkey"] == workkey_b
    assert data_c["status"] == "VALIDATED"
    assert data_c["validation_passed"] is True
    assert data_c["checks"]["check_sum_equals_100"] is True
    assert data_c["checks"]["check_mean_equals_25"] is True
    assert sha256_file(file_c) == stage_c_rec["artifact_sha"]

    # Evidence 2: SQLite Journal Lifecycle for all 3 tasks
    expected_sequence = [
        "TASK_CREATED",
        "TASK_CLAIMED",
        "TASK_STARTED",
        "RESULT_READY",
        "RESULT_ACCEPTED",
        "TASK_COMPLETE",
    ]

    for stage_info in (stage_a_rec, stage_b_rec, stage_c_rec):
        tid = stage_info["task_id"]
        task_events = [e.type.value for e in ctl.journal.events(task_id=tid)]
        assert task_events == expected_sequence, f"Task {tid} had unexpected lifecycle: {task_events}"
        task_rec = ctl.journal.task(tid)
        assert task_rec.status == TaskStatus.COMPLETE
        assert task_rec.accepted_result_id == stage_info["result_id"]

    # Evidence 3: SQLite Hash Chain Integrity
    chain_check = ctl.journal.verify_chain()
    assert chain_check.ok is True, f"Journal hash chain invalid: {chain_check}"

    # Evidence 4: Cold Replay from disk database
    ctl.stop()
    ctl_cold = _make_controller_with_verifier(home)
    assert ctl_cold.journal.verify_chain().ok is True
    for stage_info in (stage_a_rec, stage_b_rec, stage_c_rec):
        cold_task = ctl_cold.journal.task(stage_info["task_id"])
        assert cold_task.status == TaskStatus.COMPLETE
        assert cold_task.accepted_result_id == stage_info["result_id"]
    ctl_cold.stop()


def test_unmet_dependency_blocks_continuation(tmp_path):
    """Verifies fail-closed behavior if an intermediate dependency is missing."""
    home = tmp_path / "courier_home_dep"
    home.mkdir(parents=True, exist_ok=True)
    ctl = _make_controller_with_verifier(home)

    stages = [
        WorkflowStage(workkey="WORKKEY-C", stage_id="C", action="validate", depends_on=["NON-EXISTENT-B"]),
    ]
    packet = WorkflowAdmissionPacket(workflow_id="WF-BROKEN", stages=stages)
    engine = WorkflowContinuationEngine(controller=ctl, home=home)

    with pytest.raises(RuntimeError, match="CANNOT_CONTINUE: Dependency 'NON-EXISTENT-B' is not completed"):
        engine.admit_and_run(packet)

    ctl.stop()
