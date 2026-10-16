"""A020 — Real Automation Acceptance Test Suite.

Verifies:
1. THREE_DISTINCT_WORKKEYS: Three unique workkeys for Stages A, B, and C.
2. ACTUAL_PROCESS_STARTS: Real OS subprocess execution via Courier adapter runner.
3. INDEPENDENT_VERIFICATION: Independent L4 verification via adapter_verifier.
4. HUMAN_RELAY_COUNT: Strictly 0 (single user trigger, autonomous A -> B -> C).
5. DUPLICATE_EFFECTS: Exactly 1 physical execution per task (Total executions = 3).
6. RESTART_SURVIVAL: Complete persistence and recovery across cold controller reboot.
7. EXACT_SHA: Exact physical disk SHA256 matches claimed result hashes.
8. RECEIPTS: Durable on-disk receipt records written for every stage.
"""

import hashlib
import json
from pathlib import Path
import pytest

from courier_core.controller import Controller
from courier_core.state_machine import TaskStatus
from courier_core.verification import adapter_verifier
from courier_runtime.workflow_continuation import (
    WorkflowAdmissionPacket,
    WorkflowContinuationEngine,
    WorkflowStage,
    sha256_file,
)


def _make_controller(home: Path) -> Controller:
    """Boots Controller with standard independent L4 adapter verifier."""
    return Controller(home, verifier=adapter_verifier).boot()


def test_real_automation_acceptance_a020(tmp_path):
    """Full Physical Automation Acceptance: Single User Admission -> A -> B -> C."""
    home = tmp_path / "courier_a020_home"
    home.mkdir(parents=True, exist_ok=True)

    ctl = _make_controller(home)

    # 1. THREE_DISTINCT_WORKKEYS
    workkey_a = "A020-STAGE-A-PRODUCE"
    workkey_b = "A020-STAGE-B-PROCESS"
    workkey_c = "A020-STAGE-C-VALIDATE"

    assert len({workkey_a, workkey_b, workkey_c}) == 3, "THREE_DISTINCT_WORKKEYS failed"

    stages = [
        WorkflowStage(workkey=workkey_a, stage_id="A", action="produce", adapter="synthetic"),
        WorkflowStage(workkey=workkey_b, stage_id="B", action="process", adapter="synthetic", depends_on=[workkey_a]),
        WorkflowStage(workkey=workkey_c, stage_id="C", action="validate", adapter="synthetic", depends_on=[workkey_b]),
    ]

    # EIN Nutzerstart (Single user admission packet)
    packet = WorkflowAdmissionPacket(workflow_id="WF-A020-ACCEPTANCE", stages=stages)

    engine = WorkflowContinuationEngine(
        controller=ctl,
        home=home,
        worker_id="real-worker-subprocess",
        use_subprocess_runner=True,
    )

    # Run workflow autonomously
    manifest = engine.admit_and_run(packet)

    # 2. STATUS & HUMAN_RELAY_COUNT
    assert manifest["status"] == "COMPLETED"
    assert manifest["human_relay_count"] == 0, "HUMAN_RELAY_COUNT must be strictly 0"
    assert manifest["model_calls"] == 0, "MODEL_CALLS must be strictly 0"

    # 3. ACTUAL_PROCESS_STARTS (Subprocess execution check)
    assert manifest["actual_process_starts"] == 3, "ACTUAL_PROCESS_STARTS must be 3"
    assert len(engine.subprocess_runs) == 3

    for sp_run in engine.subprocess_runs:
        assert sp_run["returncode"] == 0
        assert "adapter_runner.py" in str(sp_run["cmd"])
        rep_file = Path(sp_run["report"])
        assert rep_file.is_file(), f"Runner report {rep_file} not found on disk"
        rep_data = json.loads(rep_file.read_text(encoding="utf-8"))
        assert rep_data["outcome"] == "success"

    # 4. DUPLICATE_EFFECTS (Execution counts)
    assert manifest["execution_counts"][workkey_a] == 1
    assert manifest["execution_counts"][workkey_b] == 1
    assert manifest["execution_counts"][workkey_c] == 1
    assert manifest["total_local_executions"] == 3, "DUPLICATE_EFFECTS failed: total executions != 3"

    # 5. INDEPENDENT_VERIFICATION & EXACT_SHA
    stage_a_rec = manifest["completed_stages"][workkey_a]
    stage_b_rec = manifest["completed_stages"][workkey_b]
    stage_c_rec = manifest["completed_stages"][workkey_c]

    file_a = home / stage_a_rec["artifact_rel_path"]
    file_b = home / stage_b_rec["artifact_rel_path"]
    file_c = home / stage_c_rec["artifact_rel_path"]

    assert file_a.is_file() and file_b.is_file() and file_c.is_file()

    sha_a = sha256_file(file_a)
    sha_b = sha256_file(file_b)
    sha_c = sha256_file(file_c)

    assert sha_a == stage_a_rec["artifact_sha"]
    assert sha_b == stage_b_rec["artifact_sha"]
    assert sha_c == stage_c_rec["artifact_sha"]

    # Verify task event log contains RESULT_ACCEPTED with verifier info
    for s_rec in (stage_a_rec, stage_b_rec, stage_c_rec):
        tid = s_rec["task_id"]
        task_events = list(ctl.journal.events(task_id=tid))
        event_types = [e.type.value for e in task_events]
        assert "RESULT_ACCEPTED" in event_types
        accept_event = [e for e in task_events if e.type.value == "RESULT_ACCEPTED"][0]
        assert accept_event.payload["verifier"] is not None
        assert "adapters.synthetic.verify" in accept_event.payload["verifier"]["name"]
        assert ctl.journal.task(tid).status == TaskStatus.COMPLETE

    # 6. RECEIPTS (Durable on-disk receipts)
    assert len(manifest["receipts"]) == 3
    for s_rec in (stage_a_rec, stage_b_rec, stage_c_rec):
        rcpt_path = home / s_rec["receipt_path"]
        assert rcpt_path.is_file(), f"Durable receipt missing: {rcpt_path}"
        rcpt_data = json.loads(rcpt_path.read_text(encoding="utf-8"))
        assert rcpt_data["task_id"] == s_rec["task_id"]
        assert rcpt_data["outcome"] == "success"
        assert rcpt_data["artifact_sha256"] == s_rec["artifact_sha"]

    # 7. RESTART_SURVIVAL (Cold Controller Reboot)
    ctl.stop()

    ctl_cold = _make_controller(home)
    assert ctl_cold.journal.verify_chain().ok is True

    for s_rec in (stage_a_rec, stage_b_rec, stage_c_rec):
        cold_task = ctl_cold.journal.task(s_rec["task_id"])
        assert cold_task.status == TaskStatus.COMPLETE
        assert cold_task.accepted_result_id == s_rec["result_id"]

    # Cold recovery by engine
    engine_cold = WorkflowContinuationEngine(ctl_cold, home)
    recovered = engine_cold.recover_from_ledger(packet)
    assert recovered == {
        workkey_a: "COMPLETE",
        workkey_b: "COMPLETE",
        workkey_c: "COMPLETE",
    }
    assert len(engine_cold.completed_stages) == 3

    ctl_cold.stop()
