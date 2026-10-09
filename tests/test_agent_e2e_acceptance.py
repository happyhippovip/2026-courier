import hashlib
import json
import pytest
import sys
import tempfile
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "scripts"))

from scripts.agent_warehouse import AgentCatalog, CapabilitySelector
from scripts.build_antigravity_worker_job import build_worker_job, canonical_hash
from scripts.run_antigravity_bridge import (
    AntigravityVisualStateTracker,
    AntigravityHookRunner,
    execute_bridge_task,
    run_chief_review_router,
)
import scripts.run_antigravity_bridge as rab
from scripts.courier_verifier import verify_artifact
from courier_runtime.receipt import RecoveryReceipt, validate, ReceiptError


def test_recovered_agent_full_acceptance_chain():
    """
    Verifies the complete Courier chain:
    Recovered Agent -> Capability -> Authorization -> Workkey Claim ->
    Worker Execution -> Artifact Generation -> Receipt Validation ->
    Independent Verifier PASS -> Negative Tamper Rejection.
    """
    # 1. Recovered Agent & Capability Selection
    catalog_path = repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json"
    assert catalog_path.exists(), "Agent catalog must exist"
    catalog = AgentCatalog.load(catalog_path)
    selector = CapabilitySelector(catalog)

    # Select implemented specialist agent
    explanation = selector.select_agent_for_task("asset_validation", require_implemented=True)
    assert explanation.selected_agent_id == "agent-asset-validator"
    agent_entry = next((a for a in catalog.agents if a.id == explanation.selected_agent_id), None)
    assert agent_entry is not None
    assert agent_entry.status == "implemented"

    # Verify owner file exists on disk
    for rel_path in agent_entry.owner_files:
        assert (repo_root / rel_path).exists(), f"Owner file {rel_path} must exist on disk"

    # 2. Workkey Claim & Task Building
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        workkey = "WK-V26-ACCEPTANCE-001"
        task_id = "task-v26-asset-val"

        # Authorized payload for specialist capability dispatch via Antigravity Worker Bridge
        payload = {
            "target_agent": "ANTIGRAVITY",
            "one_next_command": f"validate-asset --agent {explanation.selected_agent_id} --capability asset_validation",
            "allowed_scope": ["2026-courier"],
            "cost_policy": "ZERO_COST_ONLY",
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        }
        cmd_data = {
            "schema_version": "2.0",
            "message_id": "msg-v26-001",
            "task_id": task_id,
            "correlation_id": "corr-v26-001",
            "parent_id": None,
            "source": "chief",
            "destination": "antigravity",
            "type": "COMMAND",
            "status": "NEW",
            "created_at": "2026-10-09T17:00:00Z",
            "payload": payload,
            "payload_hash": canonical_hash(payload),
            "max_iterations": 1,
        }
        cmd_file = tmp / "cmd.json"
        cmd_file.write_text(json.dumps(cmd_data, indent=2), encoding="utf-8")

        dispatch_dir = tmp / "dispatch"
        job = build_worker_job(cmd_file, dispatch_dir)
        assert job["task_id"] == task_id

        job_path = dispatch_dir / f"{task_id}-worker-job.json"
        assert job_path.exists(), "Job file was not created"

        # 3. Worker Execution
        rab.PROCESSED_DIR = tmp / "processed"
        rab.DECISIONS_DIR = tmp / "chief-decisions"
        rab.COURIER_DIR = tmp

        tracker = AntigravityVisualStateTracker(repo_dir=tmp)
        hooks = AntigravityHookRunner(tracker)

        result_path = execute_bridge_task(job_path, hooks)
        assert result_path.exists(), "Result file missing"

        res_data = json.loads(result_path.read_text(encoding="utf-8"))
        assert res_data["status"] == "COMPLETED"
        assert res_data.get("payload", {}).get("verdict") == "PASS"

        # 4. Artifact Generation & Verifier PASS
        artifact_file = tmp / "artifact.json"
        artifact_content = json.dumps({"workkey": workkey, "task_id": task_id, "status": "VERIFIED"}, sort_keys=True)
        artifact_file.write_text(artifact_content, encoding="utf-8")
        expected_sha = hashlib.sha256(artifact_content.encode("utf-8")).hexdigest()

        # Independent Verifier check
        assert verify_artifact(str(artifact_file), expected_sha) is True, "Verifier must PASS matching artifact"

        # 5. Negative Case: Tampered artifact must FAIL Verifier
        tampered_sha = "0000000000000000000000000000000000000000000000000000000000000000"
        assert verify_artifact(str(artifact_file), tampered_sha) is False, "Verifier must FAIL tampered artifact"

        # 6. Receipt Validation
        receipt = RecoveryReceipt(
            workkey=workkey,
            session_id="sess-v26-e2e",
            incident_fingerprint="fp-clean",
            detected_state="TASK_IN_PROGRESS",
            detected_at=10000.0,
            what_failed="none",
            positive_evidence=None,
            survived={"process_alive": True, "lease_valid": True, "last_checkpoint_id": "c26"},
            action="RECONNECT_SURFACE",
            outcome="RECOVERED",
            after_snapshot="snap-v26",
            progress_after_detection=True,
        )
        validated_receipt = validate(receipt, set())
        assert validated_receipt.outcome == "RECOVERED"
        assert validated_receipt.workkey == workkey

        # 7. Negative Case: Invalid Receipt Outcome (e.g. unverified DONE) must raise ReceiptError
        invalid_receipt = RecoveryReceipt(
            workkey=workkey,
            session_id="sess-v26-e2e",
            incident_fingerprint="fp-clean",
            detected_state="TASK_IN_PROGRESS",
            detected_at=10000.0,
            what_failed="none",
            positive_evidence=None,
            survived={"process_alive": True, "lease_valid": True},
            action="RECONNECT_SURFACE",
            outcome="DONE",  # invalid unverified outcome
            after_snapshot="snap-v26",
            progress_after_detection=True,
        )
        with pytest.raises(ReceiptError, match="unknown outcome DONE"):
            validate(invalid_receipt, set())

        # 8. Chief Review Router Approval
        decision = run_chief_review_router(task_id, result_path)
        assert decision.get("verdict") == "ACCEPTED"
        assert decision.get("action") == "AUTO_APPROVE_SAFE_RESULT"

        # 9. Trusted Ledger Checkpointing via Kirby Supervisor
        from courier_runtime.kirby import KirbySupervisor
        from courier_runtime.continuation import AcceptedLog, Checkpoint

        k = KirbySupervisor(
            provider="antigravity",
            host="DESKTOP-JDPRUGR",
            session_id="sess-v26-e2e",
            state_dir=str(tmp),
        )
        accepted_log = AcceptedLog(str(tmp / "accepted.jsonl"))

        turn_summary = k.on_turn_end(
            workkey=workkey,
            state="COMPLETE",
            receipt=validated_receipt,
            owned_identities=set(),
            accepted_log=accepted_log,
            step=0,
            statement=f"Task {task_id} completed and accepted by Chief router",
        )
        assert turn_summary["state"] == "COMPLETED"
        assert turn_summary["receipt_id"] == validated_receipt.receipt_id

        ledger_file = tmp / "ledger_summary_sess-v26-e2e.json"
        assert ledger_file.exists(), "Ledger summary file must be persisted"
        ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
        assert ledger_data["receipt_id"] == validated_receipt.receipt_id
        assert ledger_data["state"] == "COMPLETED"

        # 10. Automatic Verified Safe Next Task Decision
        plan = ["asset_validation", "next_safe_downstream_task"]
        checkpoint = Checkpoint.from_log(workkey, plan=plan, log=accepted_log)
        assert checkpoint.last_accepted_step == 0

        continuation_decision = k.decide_continuation(checkpoint, lease_available=True)
        assert continuation_decision["safe"] is True
        assert continuation_decision["resume_step"] == 1
        assert continuation_decision["state"] == "RUNNING"
        assert plan[continuation_decision["resume_step"]] == "next_safe_downstream_task"

        # 11. Negative Continuation Case: Unconfirmed effect halts safely
        tampered_checkpoint = Checkpoint(
            workkey=workkey,
            plan=plan,
            last_accepted_step=0,
            attempted={"1": {"effect_class": "non_idempotent", "effect_confirmed": False}},
        )
        blocked_decision = k.decide_continuation(tampered_checkpoint, lease_available=True)
        assert blocked_decision["safe"] is False
        assert blocked_decision["state"] == "NEEDS_USER"
        assert blocked_decision["resume_step"] == 1

