"""Tests for Exact-Owned Process Recovery & Escalation Ladder (FRZ-08 / FRZ-07)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from scripts.courier_recovery import (
    build_recovery_receipt,
    execute_escalation_ladder,
    terminate_owned_process_by_pid,
    write_recovery_receipt,
)


def test_build_recovery_receipt_schema():
    """Verify recovery receipt adheres to canonical schema."""
    fake_snapshot = {
        "git": {"branch": "lane/L6-clean-machine-acceptance", "dirty_count": 0, "unpushed_count": 2},
        "owned_processes": {"worker": {"pid": 4321, "alive": True}},
        "reboot_verdict": {
            "verdict": "SAFE_TO_REBOOT",
            "safe": True,
            "reasons": [],
        },
    }
    receipt = build_recovery_receipt(
        snapshot=fake_snapshot,
        incident_type="INTERRUPTION_OR_FREEZE_RECOVERY",
        action_taken="Level 1: Passive inspection",
        outcome="COMPLETED",
    )

    assert receipt["schema_version"] == "1.0"
    assert receipt["receipt_id"].startswith("RCPT-")
    assert "hostname" in receipt["host"]
    assert "platform" in receipt["host"]
    assert "device_id" in receipt["host"]
    assert receipt["worktrees"]["branch"] == "lane/L6-clean-machine-acceptance"
    assert receipt["worktrees"]["dirty_files"] == 0
    assert receipt["worktrees"]["unpushed_commits"] == 2
    assert receipt["reboot_verdict"]["verdict"] == "SAFE_TO_REBOOT"
    assert receipt["reboot_verdict"]["safe_to_reboot"] is True


def test_write_recovery_receipt(tmp_path: Path):
    """Verify write_recovery_receipt persists JSON into run/receipts."""
    receipt = {
        "receipt_id": "RCPT-TEST-99",
        "action": "test",
    }
    receipt_file = write_recovery_receipt(receipt, tmp_path)
    assert receipt_file.is_file()
    assert receipt_file.name == "RCPT-TEST-99.json"
    data = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert data["receipt_id"] == "RCPT-TEST-99"


def test_terminate_owned_process_by_pid_invalid():
    """Verify non-positive or self PID is rejected immediately."""
    assert terminate_owned_process_by_pid(0) is False
    assert terminate_owned_process_by_pid(-1) is False


def test_execute_escalation_ladder_level1(tmp_path: Path):
    """Verify level 1 passive inspection produces receipt without terminating procs."""
    receipt = execute_escalation_ladder(level=1, app_data_dir=tmp_path)
    assert receipt["outcome"] == "STATUS_VERIFIED"
    assert "Level 1" in receipt["action_taken"]
    assert Path(receipt["receipt_file"]).is_file()


def test_execute_escalation_ladder_level3_helper(tmp_path: Path):
    """Verify level 3 targeting an owned helper."""
    # Create fake run directory with worker.pid
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "worker.pid").write_text("999999", encoding="utf-8")

    with mock.patch("scripts.courier_recovery.terminate_owned_process_by_pid", return_value=True) as mock_term:
        with mock.patch("scripts.courier_status.is_pid_alive", return_value=True):
            receipt = execute_escalation_ladder(
                target_component="worker",
                level=3,
                app_data_dir=tmp_path,
            )
            assert receipt["outcome"] == "HELPER_TERMINATED"
            assert "Level 3" in receipt["action_taken"]
            mock_term.assert_called_once_with(999999)


def test_execute_escalation_ladder_level4_all_owned(tmp_path: Path):
    """Verify level 4 tree termination targets all alive owned components."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "worker.pid").write_text("1001", encoding="utf-8")
    (run_dir / "controller.pid").write_text("1002", encoding="utf-8")

    with mock.patch("scripts.courier_recovery.terminate_owned_process_by_pid", return_value=True) as mock_term:
        with mock.patch("scripts.courier_status.is_pid_alive", return_value=True):
            receipt = execute_escalation_ladder(
                level=4,
                app_data_dir=tmp_path,
            )
            assert receipt["outcome"] == "TREES_TERMINATED"
            assert mock_term.call_count == 2
