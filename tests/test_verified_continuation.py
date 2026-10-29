import hashlib
import json
import os
import sys
from pathlib import Path
import pytest

from scripts.verified_continuation import (
    ExecutionMode,
    VerifiedContinuation,
    canonical_json_hash,
    main,
    validate_workkey,
)


@pytest.fixture
def continuation_engine(tmp_path):
    root_dir = tmp_path / "repo"
    ledger_dir = tmp_path / "ledger"
    root_dir.mkdir(parents=True, exist_ok=True)
    return VerifiedContinuation(root_dir=root_dir, ledger_dir=ledger_dir)


def test_workkey_validation():
    # Valid workkeys
    validate_workkey("WORKKEY_123")
    validate_workkey("task-456-abc")
    validate_workkey("MUSE_LEDGER_CONTINUATION")

    # Invalid workkeys (must fail closed to prevent path traversal or invalid characters)
    with pytest.raises(ValueError, match="Invalid workkey format"):
        validate_workkey("../../escape")
    with pytest.raises(ValueError, match="Invalid workkey format"):
        validate_workkey("bad key with spaces")
    with pytest.raises(ValueError, match="Invalid workkey format"):
        validate_workkey("bad/slash")


def test_claim_and_release(continuation_engine):
    workkey = "TEST_WORKKEY_01"

    # Initial claim succeeds
    assert continuation_engine.claim(workkey, owner="worker-a") is True
    claim_info = continuation_engine.is_claimed(workkey)
    assert claim_info is not None
    assert claim_info["owner"] == "worker-a"

    # Same owner can re-claim/renew
    assert continuation_engine.claim(workkey, owner="worker-a") is True

    # Competing owner cannot claim active lease
    assert continuation_engine.claim(workkey, owner="worker-b") is False

    # Non-owner cannot release
    assert continuation_engine.release(workkey, owner="worker-b") is False
    assert continuation_engine.is_claimed(workkey) is not None

    # Owner can release
    assert continuation_engine.release(workkey, owner="worker-a") is True
    assert continuation_engine.is_claimed(workkey) is None

    # Competing owner can now claim
    assert continuation_engine.claim(workkey, owner="worker-b") is True
    assert continuation_engine.release(workkey) is True


def test_mode_a_local_deterministic(continuation_engine):
    packet = {
        "task_id": "test-task-a",
        "workkey": "WORKKEY_A",
        "command": [sys.executable, "-c", "print('hello from mode a')"],
    }
    result = continuation_engine.execute_unit(packet, mode=ExecutionMode.MODE_A_LOCAL_DETERMINISTIC)
    assert result["status"] == "PASS"
    assert result["mode"] == ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value
    assert result["deterministic"] is True
    assert result["model_invoked"] is False
    assert "hello from mode a" in result["stdout"]
    assert continuation_engine.verify_result(result) is True


def test_mode_b_google_builder_fail_closed(continuation_engine):
    # In isolated test repo with NO bridge script, Mode B MUST fail closed and NOT simulate model execution
    packet = {
        "task_id": "test-task-b",
        "workkey": "WORKKEY_B",
        "instruction": "Build component safely within allowed scope",
        "allowed_scope": ["happyhippovip/2026-courier"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
    }
    result = continuation_engine.execute_unit(packet, mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)
    assert result["status"] == "UNAVAILABLE"
    assert result["mode"] == ExecutionMode.MODE_B_GOOGLE_BUILDER.value
    assert result["model_invoked"] is False
    assert result["model_driven"] is False
    assert "failing closed" in result["error"]

    # Cost policy violation must fail closed immediately
    bad_packet = dict(packet, cost_policy="UNAUTHORIZED_PAID")
    with pytest.raises(ValueError, match="Cost policy violation"):
        continuation_engine.execute_unit(bad_packet, mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)


def test_mode_b_google_builder_with_bridge(tmp_path):
    # A copied hook recorder is not a model invocation.
    root_dir = tmp_path / "repo"
    ledger_dir = tmp_path / "ledger"
    root_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = root_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    real_bridge = Path(__file__).resolve().parent.parent / "scripts" / "run_antigravity_bridge.py"
    if real_bridge.exists():
        (scripts_dir / "run_antigravity_bridge.py").write_text(real_bridge.read_text(encoding="utf-8"), encoding="utf-8")
        engine = VerifiedContinuation(root_dir=root_dir, ledger_dir=ledger_dir)
        packet = {
            "task_id": "test-task-b-real",
            "workkey": "WORKKEY_B_REAL",
            "instruction": "Build component with bridge",
            "allowed_scope": ["happyhippovip/2026-courier"],
            "cost_policy": "ZERO_COST_ONLY",
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        }
        result = engine.execute_unit(packet, mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)
        assert result["status"] == "UNAVAILABLE"
        assert result["model_invoked"] is False
        assert result["model_driven"] is False
        assert result["bridge_present"] is True
        assert "no model result" in result["error"]
        assert engine.verify_result(result) is False
        assert not (root_dir / "events" / "processed" / "test-task-b-real-result.json").exists()


def test_mode_c_autonomous_schedule(continuation_engine):
    packet = {
        "task_id": "test-task-c",
        "workkey": "WORKKEY_C",
        "instruction": "Execute background scheduled continuation",
    }
    result = continuation_engine.execute_unit(packet, mode=ExecutionMode.MODE_C_AUTONOMOUS_SCHEDULE)
    assert result["status"] == "PASS"
    assert result["mode"] == ExecutionMode.MODE_C_AUTONOMOUS_SCHEDULE.value
    assert result["coalesced"] is True
    assert result["max_pending_wake"] == 1
    assert result["manual_continue_required"] is False
    assert continuation_engine.verify_result(result) is True


def test_mode_d_recovery_resume(continuation_engine):
    workkey = "WORKKEY_D_RECOVER"

    # Missing checkpoint must fail closed
    missing_packet = {"task_id": "task-d", "workkey": workkey}
    missing_res = continuation_engine.execute_unit(missing_packet, mode=ExecutionMode.MODE_D_RECOVERY_RESUME)
    assert missing_res["status"] == "FAIL"
    assert missing_res["checkpoint_recovered"] is False

    # Create real initial unit checkpoint on disk
    unit1_result = {
        "task_id": "task-d-orig",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value,
        "status": "PASS",
        "output": "step_1_completed",
    }
    unit1_result["result_hash"] = canonical_json_hash(unit1_result)
    cp_file = continuation_engine.checkpoint(workkey, unit1_result, next_workkey="WORKKEY_NEXT")
    assert cp_file.exists()

    # Recovery resumes from existing on-disk checkpoint
    recover_packet = {"task_id": "task-d-resume", "workkey": workkey}
    recover_res = continuation_engine.execute_unit(recover_packet, mode=ExecutionMode.MODE_D_RECOVERY_RESUME)
    assert recover_res["status"] == "PASS"
    assert recover_res["checkpoint_recovered"] is True
    assert recover_res["recovered_workkey"] == workkey
    assert recover_res["next_workkey"] == "WORKKEY_NEXT"
    assert recover_res["restarted_from_zero"] is False
    assert continuation_engine.verify_result(recover_res) is True


def test_mode_d_refuses_fail_status_checkpoint(continuation_engine):
    # Fail-closed (P0): a stored checkpoint recording FAIL must NOT resume
    # as PASS progress; recovery restarts from zero instead.
    workkey = "WORKKEY_D_FAILCP"
    fail_result = {
        "task_id": "task-d-failed",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value,
        "status": "FAIL",
        "exit_code": 3,
    }
    fail_result["result_hash"] = canonical_json_hash(fail_result)
    cp_file = continuation_engine.checkpoint(workkey, fail_result)
    assert cp_file.exists()

    recover_packet = {"task_id": "task-d-resume-fail", "workkey": workkey}
    recover_res = continuation_engine.execute_unit(recover_packet, mode=ExecutionMode.MODE_D_RECOVERY_RESUME)
    assert recover_res["status"] == "FAIL"
    assert recover_res["checkpoint_recovered"] is False
    assert recover_res["restarted_from_zero"] is True
    assert recover_res["recovered_status"] == "FAIL"
    assert continuation_engine.verify_result(recover_res) is False


def test_verify_result_strict_integrity(continuation_engine):
    valid_result = {
        "task_id": "task-verify",
        "status": "PASS",
        "data": [1, 2, 3],
    }
    valid_result["result_hash"] = canonical_json_hash(valid_result)
    assert continuation_engine.verify_result(valid_result) is True

    # Tampered payload fails verification
    tampered = dict(valid_result, data=[1, 2, 999])
    assert continuation_engine.verify_result(tampered) is False

    # Tampered status fails verification
    tampered_status = dict(valid_result, status="FAIL")
    assert continuation_engine.verify_result(tampered_status) is False

    # Non-dict fails verification
    assert continuation_engine.verify_result("not a dict") is False


def test_sequential_two_unit_continuation(continuation_engine):
    u1 = {
        "task_id": "unit-1-ledger",
        "workkey": "WORKKEY_UNIT_1",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(0)"],
    }
    u2 = {
        "task_id": "unit-2-local",
        "workkey": "WORKKEY_UNIT_2",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(0)"],
    }

    report = continuation_engine.run_sequential_two_unit(u1, u2)
    assert report["status"] == "PASS"
    assert report["units_completed"] == ["WORKKEY_UNIT_1", "WORKKEY_UNIT_2"]
    assert report["sequential_handoff_proven"] is True
    assert report["manual_prompts_required"] == 0
    assert len(report["checkpoints"]) == 2

    # Checkpoint files must physically exist
    cp1_path = continuation_engine.checkpoints_dir / "WORKKEY_UNIT_1.checkpoint.json"
    cp2_path = continuation_engine.checkpoints_dir / "WORKKEY_UNIT_2.checkpoint.json"
    assert cp1_path.exists()
    assert cp2_path.exists()

    data1 = json.loads(cp1_path.read_text(encoding="utf-8"))
    assert data1["next_workkey"] == "WORKKEY_UNIT_2"
    assert data1["status"] == "PASS"


def test_sequential_two_unit_failure_releases_claim(continuation_engine):
    # P0 lease-hygiene: a failed unit 1 must raise AND release its claim (no
    # stale lease blocking retries until TTL expiry), write no checkpoint,
    # and never reach unit 2.
    u1 = {
        "task_id": "unit-1-fail",
        "workkey": "WORKKEY_FAIL_1",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(3)"],
    }
    u2 = {
        "task_id": "unit-2-ok",
        "workkey": "WORKKEY_FAIL_2",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(0)"],
    }
    with pytest.raises(RuntimeError, match="Unit 1 verification failed"):
        continuation_engine.run_sequential_two_unit(u1, u2)
    assert continuation_engine.is_claimed("WORKKEY_FAIL_1") is None
    assert continuation_engine.is_claimed("WORKKEY_FAIL_2") is None
    assert not (continuation_engine.checkpoints_dir / "WORKKEY_FAIL_1.checkpoint.json").exists()


def test_sequential_two_unit_unit2_failure_releases_claim(continuation_engine):
    # Same lease-hygiene guarantee for a failed unit 2: unit 1 stays
    # checkpointed and released, unit 2 raises and releases its claim.
    u1 = {
        "task_id": "unit-1-ok",
        "workkey": "WORKKEY_U2F_1",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(0)"],
    }
    u2 = {
        "task_id": "unit-2-fail",
        "workkey": "WORKKEY_U2F_2",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(3)"],
    }
    with pytest.raises(RuntimeError, match="Unit 2 verification failed"):
        continuation_engine.run_sequential_two_unit(u1, u2)
    assert continuation_engine.is_claimed("WORKKEY_U2F_1") is None
    assert continuation_engine.is_claimed("WORKKEY_U2F_2") is None
    assert (continuation_engine.checkpoints_dir / "WORKKEY_U2F_1.checkpoint.json").exists()
    assert not (continuation_engine.checkpoints_dir / "WORKKEY_U2F_2.checkpoint.json").exists()


def test_cli_verify_autonomy_isolated(tmp_path, capsys):
    ledger_dir = str(tmp_path / "cli_ledger")
    ret = main(["--verify-autonomy", "--ledger-dir", ledger_dir])
    assert ret == 0
    captured = capsys.readouterr()
    assert "sequential_handoff_proven" in captured.out
    assert "WORKKEY_UNIT_1_LEDGER" in captured.out
    assert "WORKKEY_UNIT_2_LOCAL" in captured.out
    checkpoint = json.loads((Path(ledger_dir) / "checkpoints" / "WORKKEY_UNIT_2_LOCAL.checkpoint.json").read_text())
    assert checkpoint["details"]["status"] == "PASS"
    assert checkpoint["details"]["model_invoked"] is False
    assert "unit-2-local" in checkpoint["details"]["stdout"]


def test_cli_workkey_failure_writes_no_checkpoint(tmp_path, capsys, monkeypatch):
    # Fail-closed (P0): a single---workkey run whose result does NOT verify
    # must not leave a durable checkpoint behind, must still release the
    # claim (no lease leak), and must exit nonzero.
    fail_result = {
        "task_id": "task-FAILKEY",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value,
        "status": "FAIL",
        "exit_code": 3,
    }
    fail_result["result_hash"] = canonical_json_hash(fail_result)
    monkeypatch.setattr(
        VerifiedContinuation,
        "execute_unit",
        lambda self, packet, mode=ExecutionMode.MODE_A_LOCAL_DETERMINISTIC: dict(fail_result),
    )
    ledger_dir = tmp_path / "fail_ledger"
    ret = main(["--workkey", "FAILKEY", "--ledger-dir", str(ledger_dir)])
    assert ret == 1
    assert not (ledger_dir / "checkpoints" / "FAILKEY.checkpoint.json").exists()
    assert VerifiedContinuation(ledger_dir=ledger_dir).is_claimed("FAILKEY") is None
    assert "no checkpoint written" in capsys.readouterr().out


def test_cli_workkey_success_still_checkpoints(tmp_path, monkeypatch):
    # Guard the other side: verified results keep working through main().
    ok_result = {
        "task_id": "task-OKKEY",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value,
        "status": "PASS",
        "exit_code": 0,
    }
    ok_result["result_hash"] = canonical_json_hash(ok_result)
    monkeypatch.setattr(
        VerifiedContinuation,
        "execute_unit",
        lambda self, packet, mode=ExecutionMode.MODE_A_LOCAL_DETERMINISTIC: dict(ok_result),
    )
    ledger_dir = tmp_path / "ok_ledger"
    ret = main(["--workkey", "OKKEY", "--ledger-dir", str(ledger_dir)])
    assert ret == 0
    cp_path = ledger_dir / "checkpoints" / "OKKEY.checkpoint.json"
    assert cp_path.exists()
    assert json.loads(cp_path.read_text(encoding="utf-8"))["status"] == "PASS"


def test_h10_expired_lease_reconcile_and_prevent_double_work(continuation_engine, monkeypatch):
    """H10: Expired claims must not be silently reclaimed if already verified or unreconciled."""
    workkey = "H10_RECON_KEY"

    # 1. Claim with 0s TTL (already expired)
    assert continuation_engine.claim(workkey, owner="worker-orig", ttl_s=0) is True

    # 2. Case A: If already verified, reclaim returns False
    result_file = continuation_engine.results_dir / f"{workkey}.result"
    result_file.write_text(json.dumps({"status": "PASS", "result": "done"}), encoding="utf-8")
    assert continuation_engine.claim(workkey, owner="worker-new") is False

    # 3. Case B: If partial exists and COURIER_AUTONOMOUS=1, fail closed
    result_file.unlink()
    partial_file = continuation_engine.results_dir / f"{workkey}.partial"
    partial_file.write_text(json.dumps({"status": "IN_FLIGHT"}), encoding="utf-8")
    monkeypatch.setenv("COURIER_AUTONOMOUS", "1")
    assert continuation_engine.claim(workkey, owner="worker-new") is False

    # 4. Case C: Once reconciled / clean, a human reclaims (VC-1: expiry alone is not proof
    #    that worker-orig stopped), then the new claim succeeds
    partial_file.unlink()
    assert continuation_engine.claim(workkey, owner="worker-new") is False
    continuation_engine.reclaim(workkey, "dennis", "worker-orig is gone, no partial left")
    assert continuation_engine.claim(workkey, owner="worker-new") is True
    claim_info = continuation_engine.is_claimed(workkey)
    assert claim_info["owner"] == "worker-new"


def test_unreadable_claim_is_not_stolen(continuation_engine):
    workkey = "UNREADABLE_CLAIM"
    claim_file = continuation_engine.claims_dir / f"{workkey}.claim"
    original = b"not-json\n"
    claim_file.write_bytes(original)
    assert continuation_engine.claim(workkey, owner="worker-b") is False
    assert claim_file.read_bytes() == original
    seen = continuation_engine.is_claimed(workkey)
    assert seen is not None
    assert seen.get("owner") != "worker-b"


def test_claim_without_expiry_is_not_stolen(continuation_engine):
    workkey = "NO_EXPIRY_CLAIM"
    claim_file = continuation_engine.claims_dir / f"{workkey}.claim"
    original = json.dumps({"workkey": workkey, "owner": "worker-a", "ttl_s": 3600})
    claim_file.write_text(original, encoding="utf-8")
    assert continuation_engine.claim(workkey, owner="worker-b") is False
    assert claim_file.read_text(encoding="utf-8") == original
    assert continuation_engine.is_claimed(workkey)["owner"] == "worker-a"


def test_bool_claim_timestamp_is_not_stolen(continuation_engine):
    workkey = "BOOL_TS_CLAIM"
    claim_file = continuation_engine.claims_dir / f"{workkey}.claim"
    original = json.dumps(
        {"workkey": workkey, "owner": "worker-a", "created_at_ts": True, "ttl_s": 3600}
    )
    claim_file.write_text(original, encoding="utf-8")
    assert continuation_engine.claim(workkey, owner="worker-b") is False
    data = json.loads(claim_file.read_text(encoding="utf-8"))
    assert data["owner"] == "worker-a"
    assert data["created_at_ts"] is True


def test_symlink_claim_is_not_adopted(continuation_engine, tmp_path):
    workkey = "LINK_CLAIM"
    outside = tmp_path / "outside-claim.txt"
    outside.write_text("keep", encoding="utf-8")
    claim_file = continuation_engine.claims_dir / f"{workkey}.claim"
    try:
        claim_file.symlink_to(outside)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Creating symlinks on Windows requires developer mode or administrator privilege")
        raise
    assert continuation_engine.claim(workkey, owner="worker-b") is False
    assert claim_file.is_symlink()
    assert outside.read_text(encoding="utf-8") == "keep"
    assert continuation_engine.is_claimed(workkey).get("unreadable") is True


def test_expired_numeric_claim_can_be_reclaimed(continuation_engine):
    workkey = "EXPIRED_CLAIM"
    claim_file = continuation_engine.claims_dir / f"{workkey}.claim"
    claim_file.write_text(
        json.dumps({"workkey": workkey, "owner": "worker-a", "created_at_ts": 0, "ttl_s": 1}),
        encoding="utf-8",
    )
    # Expiry alone is not proof that worker-a's unit stopped (VC-1): a human reclaims first.
    assert continuation_engine.claim(workkey, owner="worker-b") is False
    continuation_engine.reclaim(workkey, "dennis", "worker-a is gone")
    assert continuation_engine.claim(workkey, owner="worker-b") is True
    assert continuation_engine.is_claimed(workkey)["owner"] == "worker-b"

