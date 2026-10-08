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
