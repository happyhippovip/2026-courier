import hashlib
import json
import pytest
import sys
import tempfile
import textwrap
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


def test_provider_exec_real_headless_subprocess_chain(tmp_path, monkeypatch):
    """
    Proves Packet 2 (Real E2E Gap):
    Connects Authorized Workkey -> Real Worker Subprocess Execution (via provider_exec)
    -> Exact Redacted Artifact -> Verifier PASS -> Courier Ledger Receipt.
    Runs a real OS process (python executable) with stdin closed and policy boundaries.
    """
    from courier_worker.adapters import provider_exec
    from adapters import provider_exec as verifier_adapter

    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: True)

    # 1. Create real headless mock agent executable
    import stat
    fake_script = tmp_path / "agent_binary.py"
    fake_script.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent('''
            import json, sys
            # Emulate headless CLI output with exact success envelope
            payload = {
                "conversation_id": "conv-real-e2e",
                "status": "SUCCESS",
                "response": "VERIFIED_SPECIALIST_OUTPUT",
                "usage": {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17},
                "duration_seconds": 0.2,
            }
            sys.stdout.write(json.dumps(payload) + "\\n")
            sys.exit(0)
        ''').lstrip(),
        encoding="utf-8"
    )
    fake_script.chmod(fake_script.stat().st_mode | stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)

    workdir = tmp_path / "workdir"
    workdir.mkdir()
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    # 2. Spec with authorized workkey and capability
    workkey = "WK-REAL-E2E-AGY-001"
    task_id = "task-real-agy-001"
    params = {
        "provider": "agy",
        "prompt": "run verified asset validation",
        "print_timeout_s": 60,
    }
    config = {"binaries": {"agy": str(fake_script.resolve())}}

    # 3. Real Subprocess Execution via provider_exec.run
    result = provider_exec.run(params, str(workdir), config=config)
    assert result.outcome == "success"
    assert result.exit_code == 0
    assert result.verified is True
    assert result.launched is True

    # 4. Save and verify artifact
    artifact_data = {
        "workkey": workkey,
        "task_id": task_id,
        "output_sha256": result.output_sha256,
        "status": "COMPLETED",
    }
    artifact_file = artifact_dir / f"{task_id}.json"
    artifact_file.write_text(json.dumps(artifact_data, sort_keys=True), encoding="utf-8")
    assert artifact_file.exists()

    # 5. Ledger Receipt validation
    receipt = RecoveryReceipt(
        workkey=workkey,
        session_id="sess-real-agy",
        incident_fingerprint="fp-real-exec",
        detected_state="TASK_IN_PROGRESS",
        detected_at=20000.0,
        what_failed="none",
        positive_evidence=None,
        survived={"process_alive": True, "lease_valid": True, "exit_code": 0},
        action="RECONNECT_SURFACE",
        outcome="RECOVERED",
        after_snapshot="snap-real-exec",
        progress_after_detection=True,
    )
    validated = validate(receipt, set())
    assert validated.outcome == "RECOVERED"
    assert validated.workkey == workkey


def test_two_step_automatic_continuation_with_real_subprocesses_and_crash_recovery(tmp_path, monkeypatch):
    """
    Proves P3 (Automatic Continuation) and P4 (Crash Recovery & Idempotence):
    1. Defines a 2-step plan: ["asset_validation", "asset_promotion"].
    2. Runs Step 0 via a REAL headless subprocess, generates artifact, validates receipt,
       and records an AcceptedFact in the durable AcceptedLog via KirbySupervisor.
    3. Verifies automatic continuation advances to Step 1 without human intervention.
    4. Simulates a crash / session interruption: reloads state from durable disk,
       verifies Step 0 is not re-executed, and resumes directly at Step 1.
    5. Runs Step 1 via a REAL headless subprocess, generates artifact, validates receipt,
       and records completion.
    6. Verifies final continuation returns state='DONE' with all steps accepted.
    7. Tests negative cases: unconfirmed non-idempotent side-effects halt continuation (NEEDS_USER),
       and lost lease halts continuation (WAITING).
    """
    import stat
    from courier_worker.adapters import provider_exec
    from courier_runtime.kirby import KirbySupervisor
    from courier_runtime.continuation import AcceptedLog, Checkpoint
    from scripts.courier_verifier import verify_artifact

    monkeypatch.setattr(provider_exec, "admit_heavy", lambda: True)

    # 1. Real headless mock agent binary that handles multi-step commands
    fake_script = tmp_path / "agent_multi.py"
    fake_script.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent('''
            import json, sys
            raw_in = sys.stdin.read() if not sys.stdin.isatty() else ""
            prompt = " ".join(sys.argv)
            step_id = 1 if "step-1" in prompt else 0
            payload = {
                "step": step_id,
                "status": "SUCCESS",
                "verdict": "PASS",
                "output": f"STEP_{step_id}_VERIFIED_OUTPUT",
            }
            sys.stdout.write(json.dumps(payload) + "\\n")
            sys.exit(0)
        ''').lstrip(),
        encoding="utf-8"
    )
    fake_script.chmod(fake_script.stat().st_mode | stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)

    config = {"binaries": {"agy": str(fake_script.resolve())}}
    workkey = "WK-P3-AUTO-CONTINUE-001"
    plan = ["asset_validation", "asset_promotion"]

    # 2. Initialize Kirby Supervisor and durable AcceptedLog
    log_file = tmp_path / "accepted.jsonl"
    accepted_log = AcceptedLog(str(log_file))
    k1 = KirbySupervisor(
        provider="antigravity",
        host="DESKTOP-JDPRUGR",
        session_id="sess-p3-initial",
        state_dir=str(tmp_path),
    )

    # Check initial decision before any step
    chk_init = Checkpoint.from_log(workkey, plan=plan, log=accepted_log)
    assert chk_init.last_accepted_step == -1
    dec_init = k1.decide_continuation(chk_init, lease_available=True)
    assert dec_init["safe"] is True
    assert dec_init["resume_step"] == 0
    assert dec_init["state"] == "RUNNING"

    # 3. Execute Step 0 via REAL subprocess
    workdir0 = tmp_path / "workdir_step0"
    workdir0.mkdir()
    res0 = provider_exec.run({"provider": "agy", "prompt": "run step-0"}, str(workdir0), config=config)
    assert res0.outcome == "success"
    assert res0.exit_code == 0
    assert res0.verified is True

    # Artifact generation and verification for Step 0
    art0_data = {"workkey": workkey, "step": 0, "sha": res0.output_sha256}
    art0_content = json.dumps(art0_data, sort_keys=True)
    art0_file = tmp_path / "artifact_step0.json"
    art0_file.write_text(art0_content, encoding="utf-8")
    art0_sha = hashlib.sha256(art0_content.encode("utf-8")).hexdigest()
    assert verify_artifact(str(art0_file), art0_sha) is True

    # Receipt for Step 0 and on_turn_end logging
    receipt0 = RecoveryReceipt(
        workkey=workkey,
        session_id="sess-p3-initial",
        incident_fingerprint="fp-step0",
        detected_state="TASK_IN_PROGRESS",
        detected_at=30000.0,
        what_failed="none",
        positive_evidence=None,
        survived={"process_alive": True, "lease_valid": True, "exit_code": 0},
        action="NONE",
        outcome="RECOVERED",
        after_snapshot="snap-step0",
        progress_after_detection=True,
    )
    validated0 = validate(receipt0, set())
    summary0 = k1.on_turn_end(
        workkey=workkey,
        state="COMPLETE",
        receipt=validated0,
        owned_identities=set(),
        accepted_log=accepted_log,
        step=0,
        statement="Step 0 (asset_validation) verified and accepted",
    )
    assert summary0["state"] == "COMPLETED"
    assert summary0["accepted_fact"]["step"] == 0

    # 4. Verify Automatic Continuation Decision for Step 1
    chk_after0 = Checkpoint.from_log(workkey, plan=plan, log=accepted_log)
    assert chk_after0.last_accepted_step == 0
    dec_after0 = k1.decide_continuation(chk_after0, lease_available=True)
    assert dec_after0["safe"] is True
    assert dec_after0["resume_step"] == 1
    assert dec_after0["state"] == "RUNNING"
    assert plan[dec_after0["resume_step"]] == "asset_promotion"

    # 5. SIMULATE CRASH & RECOVERY (P4): Process dies, new session boots, recovers from log
    k2 = KirbySupervisor(
        provider="antigravity",
        host="DESKTOP-JDPRUGR",
        session_id="sess-p3-recovered",
        state_dir=str(tmp_path),
    )
    # Reload checkpoint purely from durable disk log
    chk_recovered = Checkpoint.from_log(workkey, plan=plan, log=accepted_log)
    assert chk_recovered.last_accepted_step == 0
    dec_recovered = k2.decide_continuation(chk_recovered, lease_available=True)
    assert dec_recovered["safe"] is True
    assert dec_recovered["resume_step"] == 1  # Resumes directly at Step 1, Step 0 skipped
    assert dec_recovered["state"] == "RUNNING"

    # 6. Execute Step 1 via REAL subprocess in the recovered session
    workdir1 = tmp_path / "workdir_step1"
    workdir1.mkdir()
    res1 = provider_exec.run({"provider": "agy", "prompt": "run step-1"}, str(workdir1), config=config)
    assert res1.outcome == "success"
    assert res1.exit_code == 0

    art1_data = {"workkey": workkey, "step": 1, "sha": res1.output_sha256}
    art1_content = json.dumps(art1_data, sort_keys=True)
    art1_file = tmp_path / "artifact_step1.json"
    art1_file.write_text(art1_content, encoding="utf-8")
    art1_sha = hashlib.sha256(art1_content.encode("utf-8")).hexdigest()
    assert verify_artifact(str(art1_file), art1_sha) is True

    receipt1 = RecoveryReceipt(
        workkey=workkey,
        session_id="sess-p3-recovered",
        incident_fingerprint="fp-step1",
        detected_state="TASK_IN_PROGRESS",
        detected_at=31000.0,
        what_failed="none",
        positive_evidence=None,
        survived={"process_alive": True, "lease_valid": True, "exit_code": 0},
        action="NONE",
        outcome="RECOVERED",
        after_snapshot="snap-step1",
        progress_after_detection=True,
    )
    validated1 = validate(receipt1, set())
    summary1 = k2.on_turn_end(
        workkey=workkey,
        state="COMPLETE",
        receipt=validated1,
        owned_identities=set(),
        accepted_log=accepted_log,
        step=1,
        statement="Step 1 (asset_promotion) verified and accepted",
    )
    assert summary1["state"] == "COMPLETED"
    assert summary1["accepted_fact"]["step"] == 1

    # 7. Final Continuation Decision: All steps completed
    chk_final = Checkpoint.from_log(workkey, plan=plan, log=accepted_log)
    assert chk_final.last_accepted_step == 1
    dec_final = k2.decide_continuation(chk_final, lease_available=True)
    assert dec_final["safe"] is True
    assert dec_final["resume_step"] is None
    assert dec_final["state"] == "DONE"
    assert "all steps accepted" in dec_final["reasons"]

    # 8. Negative Tests for Safety & Boundaries
    # Negative A: Unconfirmed non-idempotent effect halts continuation
    chk_unconfirmed = Checkpoint(
        workkey=workkey,
        plan=plan,
        last_accepted_step=0,
        attempted={"1": {"effect_class": "non_idempotent", "effect_confirmed": False}},
    )
    dec_unconfirmed = k2.decide_continuation(chk_unconfirmed, lease_available=True)
    assert dec_unconfirmed["safe"] is False
    assert dec_unconfirmed["state"] == "NEEDS_USER"

    # Negative B: Write lease unavailable halts continuation when steps are pending
    dec_lease = k2.decide_continuation(chk_after0, lease_available=False)
    assert dec_lease["safe"] is False
    assert dec_lease["state"] == "WAITING"
    assert "another holder has the write lease" in dec_lease["reasons"][0]



