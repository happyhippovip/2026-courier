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
)


@pytest.fixture
def continuation_engine(tmp_path):
    root_dir = tmp_path / "repo"
    ledger_dir = tmp_path / "ledger"
    root_dir.mkdir(parents=True, exist_ok=True)
    return VerifiedContinuation(root_dir=root_dir, ledger_dir=ledger_dir)


def test_claim_and_release(continuation_engine):
    workkey = "TEST-WORKKEY-01"

    # Initial claim succeeds
    assert continuation_engine.claim(workkey, owner="worker-a") is True
    claim_info = continuation_engine.is_claimed(workkey)
    assert claim_info is not None
    assert claim_info["owner"] == "worker-a"

    # Same owner can re-claim/renew
    assert continuation_engine.claim(workkey, owner="worker-a") is True

    # Competing owner cannot claim active lease
    assert continuation_engine.claim(workkey, owner="worker-b") is False

    # Release clears lease
    assert continuation_engine.release(workkey) is True
    assert continuation_engine.is_claimed(workkey) is None

    # Competing owner can now claim
    assert continuation_engine.claim(workkey, owner="worker-b") is True
    assert continuation_engine.release(workkey) is True


def test_mode_a_local_deterministic(continuation_engine):
    packet = {
        "task_id": "test-task-a",
        "workkey": "WORKKEY-A",
        "command": [sys.executable, "-c", "print('hello from mode a')"],
    }
    result = continuation_engine.execute_unit(packet, mode=ExecutionMode.MODE_A_LOCAL_DETERMINISTIC)
    assert result["status"] == "PASS"
    assert result["mode"] == ExecutionMode.MODE_A_LOCAL_DETERMINISTIC.value
    assert result["deterministic"] is True
    assert result["model_invoked"] is False
    assert "hello from mode a" in result["stdout"]
    assert continuation_engine.verify_result(result) is True


def test_mode_b_google_builder(continuation_engine):
    packet = {
        "task_id": "test-task-b",
        "workkey": "WORKKEY-B",
        "instruction": "Build component safely within allowed scope",
        "allowed_scope": ["happyhippovip/2026-courier"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
    }
    result = continuation_engine.execute_unit(packet, mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)
    assert result["status"] == "PASS"
    assert result["mode"] == ExecutionMode.MODE_B_GOOGLE_BUILDER.value
    assert result["model_invoked"] is True
    assert continuation_engine.verify_result(result) is True

    # Cost policy violation must fail closed
    bad_packet = dict(packet, cost_policy="UNAUTHORIZED_PAID")
    with pytest.raises(ValueError, match="Cost policy violation"):
        continuation_engine.execute_unit(bad_packet, mode=ExecutionMode.MODE_B_GOOGLE_BUILDER)


def test_mode_c_autonomous_schedule(continuation_engine):
    packet = {
        "task_id": "test-task-c",
        "workkey": "WORKKEY-C",
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
    packet = {
        "task_id": "test-task-d",
        "workkey": "WORKKEY-D",
        "steps": ["step0_claim", "step1_build", "step2_verify", "step3_publish"],
        "last_accepted_step": 1,
    }
    result = continuation_engine.execute_unit(packet, mode=ExecutionMode.MODE_D_RECOVERY_RESUME)
    assert result["status"] == "PASS"
    assert result["mode"] == ExecutionMode.MODE_D_RECOVERY_RESUME.value
    assert result["checkpoint_recovered"] is True
    assert result["resumed_from"] == 2
    assert result["restarted_from_zero"] is False
    assert continuation_engine.verify_result(result) is True


def test_sequential_two_unit_continuation(continuation_engine):
    u1 = {
        "task_id": "unit-1-ledger",
        "workkey": "WORKKEY-UNIT-1",
        "mode": ExecutionMode.MODE_A_LOCAL_DETERMINISTIC,
        "command": [sys.executable, "-c", "import sys; sys.exit(0)"],
    }
    u2 = {
        "task_id": "unit-2-builder",
        "workkey": "WORKKEY-UNIT-2",
        "mode": ExecutionMode.MODE_B_GOOGLE_BUILDER,
        "instruction": "Build next verified unit",
        "allowed_scope": ["happyhippovip/2026-courier"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
    }

    report = continuation_engine.run_sequential_two_unit(u1, u2)
    assert report["status"] == "PASS"
    assert report["units_completed"] == ["WORKKEY-UNIT-1", "WORKKEY-UNIT-2"]
    assert report["sequential_handoff_proven"] is True
    assert report["manual_prompts_required"] == 0
    assert len(report["checkpoints"]) == 2

    # Checkpoint files must physically exist
    cp1_path = continuation_engine.checkpoints_dir / "WORKKEY-UNIT-1.checkpoint.json"
    cp2_path = continuation_engine.checkpoints_dir / "WORKKEY-UNIT-2.checkpoint.json"
    assert cp1_path.exists()
    assert cp2_path.exists()

    data1 = json.loads(cp1_path.read_text(encoding="utf-8"))
    assert data1["next_workkey"] == "WORKKEY-UNIT-2"
    assert data1["status"] == "PASS"


def test_cli_verify_autonomy(capsys):
    ret = main(["--verify-autonomy"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "sequential_handoff_proven" in captured.out
    assert "WORKKEY-UNIT-1-LEDGER" in captured.out
    assert "WORKKEY-UNIT-2-BUILDER" in captured.out
