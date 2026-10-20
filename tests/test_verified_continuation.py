import hashlib
import json
import os
import sys
from pathlib import Path
import pytest

from scripts.verified_continuation import (
    MARATHON_20_WORKKEYS,
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
    # When bridge script physically exists, real hooks are executed
    root_dir = tmp_path / "repo"
    ledger_dir = tmp_path / "ledger"
    root_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = root_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Copy real bridge script
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
        assert result["status"] == "PASS"
        assert result["model_invoked"] is True
        assert result["model_driven"] is True
        assert engine.verify_result(result) is True


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


def test_cli_verify_autonomy_isolated(tmp_path, capsys):
    ledger_dir = str(tmp_path / "cli_ledger")
    ret = main(["--verify-autonomy", "--ledger-dir", ledger_dir])
    assert ret == 0
    captured = capsys.readouterr()
    assert "sequential_handoff_proven" in captured.out
    assert "WORKKEY_UNIT_1_LEDGER" in captured.out
    assert "WORKKEY_UNIT_2_BUILDER" in captured.out


def test_marathon_20_sequential_continuation(continuation_engine):
    report = continuation_engine.run_marathon_20()
    assert report["status"] == "PASS"
    assert report["marathon_count"] == 20
    assert len(report["units_completed"]) == 20
    assert report["units_completed"] == MARATHON_20_WORKKEYS
    assert report["sequential_handoff_proven"] is True
    assert report["manual_prompts_required"] == 0
    assert len(report["checkpoints"]) == 20
    assert len(report["result_hashes"]) == 20

    # Verify first and last checkpoint files exist
    cp_first = continuation_engine.checkpoints_dir / f"{MARATHON_20_WORKKEYS[0]}.checkpoint.json"
    cp_last = continuation_engine.checkpoints_dir / f"{MARATHON_20_WORKKEYS[-1]}.checkpoint.json"
    assert cp_first.exists()
    assert cp_last.exists()

    d_first = json.loads(cp_first.read_text(encoding="utf-8"))
    assert d_first["next_workkey"] == MARATHON_20_WORKKEYS[1]

    d_last = json.loads(cp_last.read_text(encoding="utf-8"))
    assert d_last["next_workkey"] is None


def test_cli_verify_marathon_20_isolated(tmp_path, capsys):
    ledger_dir = str(tmp_path / "cli_marathon_ledger")
    ret = main(["--verify-marathon-20", "--ledger-dir", ledger_dir])
    assert ret == 0
    captured = capsys.readouterr()
    assert "MARATHON_01_TRUTH_EVIDENCE" in captured.out
    assert "MARATHON_20_MONEY_FACTORY_GOAL" in captured.out


def test_cli_verify_stress_chain_isolated(tmp_path, capsys):
    ledger_dir = str(tmp_path / "cli_stress_ledger")
    ret = main(["--verify-stress-chain", "--ledger-dir", ledger_dir])
    assert ret == 0
    captured = capsys.readouterr()
    assert "WK_CACHE_POISON_IMMUNITY" in captured.out
    assert "stress_performance_proven" in captured.out


def test_cli_verify_result_customs_isolated(tmp_path, capsys):
    ledger_dir = str(tmp_path / "cli_customs_ledger")
    ret = main(["--verify-result-customs", "--ledger-dir", ledger_dir])
    assert ret == 0
    captured = capsys.readouterr()
    assert "WK_ATOMIC_RESULT_HARVESTER" in captured.out
    assert "result_customs_proven" in captured.out


def test_cli_verify_chain_a_b_c_isolated(tmp_path, capsys):
    ledger_dir = str(tmp_path / "cli_chain_ledger")
    ret = main(["--verify-chain-a-b-c", "--ledger-dir", ledger_dir])
    assert ret == 0
    captured = capsys.readouterr()
    assert "WORKKEY_CHAIN_A_LOCAL" in captured.out
    assert "WORKKEY_CHAIN_B_BUILDER" in captured.out
    assert "WORKKEY_CHAIN_C_SCHEDULE" in captured.out


def test_p0_no_false_pass_timeout_lease_and_cost_guards(continuation_engine):
    # 1. P0-1: Failed checkpoint must NEVER recover as PASS in Mode D
    failed_res = {
        "task_id": "task-fail-orig",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value,
        "status": "FAIL",
        "exit_code": 1,
    }
    failed_res["result_hash"] = canonical_json_hash(failed_res)
    continuation_engine.checkpoint("WORKKEY_FAILED_CP", failed_res)

    rec = continuation_engine.execute_unit(
        {"task_id": "task-rec", "workkey": "WORKKEY_FAILED_CP"},
        mode=ExecutionMode.MODE_D_RECOVERY_RESUME,
    )
    assert rec["status"] == "FAIL"
    assert rec["checkpoint_recovered"] is False
    assert continuation_engine.verify_result(rec) is False

    # 2. P0-2: Timeout in Mode A returns deterministic FAIL and marks non-idempotent as retryable=False
    timeout_res = continuation_engine.execute_unit(
        {
            "task_id": "task-timeout",
            "command": [sys.executable, "-c", "import time; time.sleep(2)"],
            "timeout_s": 0.1,
            "idempotent": False,
        },
        mode=ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
    )
    assert timeout_res["status"] == "FAIL"
    assert timeout_res["timed_out"] is True
    assert timeout_res["retryable"] is False
    assert continuation_engine.verify_result(timeout_res) is False

    # 3. P0-3: Lease must be immediately released when run_sequential_two_unit fails
    u1_fail = {
        "task_id": "u1-fail",
        "workkey": "WK_U1_FAIL_LEASE",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(1)"],
    }
    u2_ok = {
        "task_id": "u2-ok",
        "workkey": "WK_U2_NEVER_CLAIMED",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(0)"],
    }
    with pytest.raises(RuntimeError, match="Unit 1 verification failed"):
        continuation_engine.run_sequential_two_unit(u1_fail, u2_ok)
    assert continuation_engine.is_claimed("WK_U1_FAIL_LEASE") is None
    assert continuation_engine.is_claimed("WK_U2_NEVER_CLAIMED") is None

    # 4. P0-4: Mode B rejects unknown (None, NaN) or positive estimated_cost_eur
    for bad_cost in (None, float("nan"), -0.01, 0.01):
        with pytest.raises(ValueError, match="Cost policy violation"):
            continuation_engine.execute_unit(
                {
                    "task_id": "task-bad-cost",
                    "workkey": "WK_BAD_COST",
                    "cost_policy": "ZERO_COST_ONLY",
                    "estimated_cost_eur": bad_cost,
                },
                mode=ExecutionMode.MODE_B_GOOGLE_BUILDER,
            )


def test_p0_v64_checkpoint_workkey_mismatch_and_duplicate_task_id_guards(continuation_engine):
    # 1. Foreign checkpoint copied under another workkey filename must fail recovery
    foreign_res = {
        "task_id": "task-foreign-orig",
        "workkey": "WK_FOREIGN_ORIGIN",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value,
        "status": "PASS",
        "exit_code": 0,
    }
    foreign_res["result_hash"] = canonical_json_hash(foreign_res)
    continuation_engine.checkpoint("WK_FOREIGN_ORIGIN", foreign_res)

    # Copy foreign checkpoint file to a target workkey filename
    src_cp = continuation_engine.checkpoints_dir / "WK_FOREIGN_ORIGIN.checkpoint.json"
    dst_cp = continuation_engine.checkpoints_dir / "WK_STOLEN_TARGET.checkpoint.json"
    dst_cp.write_text(src_cp.read_text(encoding="utf-8"), encoding="utf-8")

    rec = continuation_engine.execute_unit(
        {"task_id": "task-target", "workkey": "WK_STOLEN_TARGET"},
        mode=ExecutionMode.MODE_D_RECOVERY_RESUME,
    )
    assert rec["status"] == "FAIL"
    assert rec["checkpoint_recovered"] is False
    assert "workkey mismatch" in rec["error"]

    # 2. verify_result rejects result whose task_id or workkey does not match expected unit
    valid_res = {
        "task_id": "task-expected-1",
        "workkey": "WK_EXPECTED_1",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value,
        "status": "PASS",
        "exit_code": 0,
    }
    valid_res["result_hash"] = canonical_json_hash(valid_res)
    assert continuation_engine.verify_result(
        valid_res, expected_task_id="task-expected-1", expected_workkey="WK_EXPECTED_1"
    ) is True
    assert continuation_engine.verify_result(
        valid_res, expected_task_id="task-other-2", expected_workkey="WK_EXPECTED_1"
    ) is False
    assert continuation_engine.verify_result(
        valid_res, expected_task_id="task-expected-1", expected_workkey="WK_OTHER_2"
    ) is False

    # 3. Duplicate task_id or duplicate workkey in sequential chain must raise ValueError
    u1 = {
        "task_id": "dup-task-1",
        "workkey": "WK_CHAIN_1",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
    }
    u2_dup_task = {
        "task_id": "dup-task-1",
        "workkey": "WK_CHAIN_2",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
    }
    with pytest.raises(ValueError, match="Duplicate task_id"):
        continuation_engine.run_sequential_two_unit(u1, u2_dup_task)
    with pytest.raises(ValueError, match="Duplicate task_id"):
        continuation_engine.run_sequential_chain([u1, u2_dup_task])


def test_mode_b_google_builder_payload_validation_rejects_malformed_inputs(continuation_engine):
    base_packet = {
        "task_id": "valid-task-b",
        "workkey": "WORKKEY_B",
        "instruction": "Build component",
        "allowed_scope": ["happyhippovip/2026-courier"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
    }

    # 1. Invalid task_id
    with pytest.raises(ValueError, match="task_id"):
        continuation_engine.execute_unit(dict(base_packet, task_id=""), mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)
    with pytest.raises(ValueError, match="invalid characters"):
        continuation_engine.execute_unit(dict(base_packet, task_id="bad task!"), mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)

    # 2. Invalid instruction (empty or NUL)
    with pytest.raises(ValueError, match="instruction"):
        continuation_engine.execute_unit(dict(base_packet, instruction="   "), mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)
    with pytest.raises(ValueError, match="instruction"):
        continuation_engine.execute_unit(dict(base_packet, instruction="bad\x00instr"), mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)

    # 3. Invalid allowed_scope (empty, traversal, drive, UNC)
    with pytest.raises(ValueError, match="allowed_scope"):
        continuation_engine.execute_unit(dict(base_packet, allowed_scope=[]), mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)
    with pytest.raises(ValueError, match="allowed_scope"):
        continuation_engine.execute_unit(dict(base_packet, allowed_scope="not-a-list"), mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)
    for bad_scope in ["../escape", "C:/Windows", "\\\\evil\\share", "/absolute/path"]:
        with pytest.raises(ValueError, match="escapes sandbox or is unsafe"):
            continuation_engine.execute_unit(dict(base_packet, allowed_scope=[bad_scope]), mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)
