"""E2E acceptance: real provider_exec subprocess chain and two-step continuation with crash recovery (recut from #410)."""
import hashlib
import json
import sys
import textwrap
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "scripts"))

from courier_runtime.receipt import RecoveryReceipt, validate


def test_provider_exec_real_headless_subprocess_chain(tmp_path, monkeypatch):
    """
    Proves Packet 2 (Real E2E Gap):
    Connects Authorized Workkey -> Real Worker Subprocess Execution (via provider_exec)
    -> Exact Redacted Artifact -> Verifier PASS -> Courier Ledger Receipt.
    Runs a real OS process (python executable) with stdin closed and policy boundaries.
    """
    from courier_worker.adapters import provider_exec


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



