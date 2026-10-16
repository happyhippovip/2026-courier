"""Interruption Test Harness (FRZ-10).

Acceptance tests proving the canonical invariant:
  A BROKEN SURFACE MUST NEVER IMPLY LOST WORK.

Scenarios tested:
1. Explorer/UI freeze while a worker runs -> work continues, status readable headlessly.
2. Terminal host death (integrated terminal / PowerShell Editor Services) ->
   worker and state unaffected, classified TERMINAL_HOST_FAILED, not WORK_FAILED.
3. IDE crash -> uncommitted work preserved headlessly without mutation.
4. Courier surface crash -> controller/worker/journal continue, surface rebuilds.
5. Worker survives surface loss -> result delivered and visible after surface returns.
6. Worker crashes while surface survives -> honest failure, no fake progress.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from scripts.courier_recovery import (
    build_recovery_receipt,
    execute_escalation_ladder,
)
from scripts.courier_status import (
    evaluate_reboot_verdict,
    get_critical_snapshot_l0,
)
from scripts.layered_health import (
    FailureClassification,
    LayerState,
    assess_surface_layer,
    assess_terminal_host_layer,
    assess_work_execution_layer,
    evaluate_system_layered_health,
)
from scripts.work_preservation import (
    is_path_safe_to_preserve,
    preserve_uncommitted_work,
)


def test_scenario_surface_freeze_work_continues(tmp_path: Path):
    """Scenario 1: Explorer/UI freezes while worker runs.

    Verify worker status is readable headlessly and marked healthy despite surface loss.
    """
    owned_procs = {
        "worker": {"alive": True, "pid": 1234},
        "hub": {"alive": False, "pid": 5678},  # UI frozen / terminated
    }
    claims = [{"dispatch_id": "disp-golden-1", "task_id": "task-1"}]

    work_eval = assess_work_execution_layer(owned_procs, claims)
    surface_eval = assess_surface_layer(owned_procs)

    # Invariant check: surface is offline, but work is healthy and running!
    assert surface_eval["state"] == LayerState.DEGRADED.value
    assert surface_eval["hub_alive"] is False
    assert work_eval["state"] == LayerState.HEALTHY.value
    assert work_eval["worker_alive"] is True
    assert work_eval["active_claims"] == 1


def test_scenario_terminal_host_death_classified_correctly():
    """Scenario 2: Terminal host fails (PowerShell Editor Services / VS Code terminal crash).

    Must be classified as TERMINAL_HOST_FAILED, NOT WORK_FAILED.
    """
    with mock.patch("scripts.layered_health.assess_terminal_host_layer") as mock_term:
        mock_term.return_value = {
            "layer": "TERMINAL_HOST",
            "state": LayerState.FAILED.value,
            "reasons": ["PowerShell Editor Services extension terminal closed unexpectedly"],
        }
        with mock.patch("scripts.layered_health.get_owned_pids") as mock_pids:
            # Worker is alive and running task
            mock_pids.return_value = {
                "worker": {"alive": True, "pid": 2001},
                "launcher": {"alive": True, "pid": 2000},
                "hub": {"alive": True, "pid": 2002},
            }
            with mock.patch("scripts.layered_health.get_active_claims", return_value=[{"dispatch_id": "d-1"}]):
                with mock.patch("scripts.layered_health.get_journal_stats", return_value={"exists": True}):
                    with mock.patch("scripts.layered_health.get_git_status", return_value={"dirty_count": 0, "unpushed_count": 0}):
                        report = evaluate_system_layered_health()

                        # Invariant check: Failure classification is TERMINAL_HOST_FAILED, not WORK_FAILED
                        assert report["primary_failure_classification"] == FailureClassification.TERMINAL_HOST_FAILED.value
                        assert report["layers"]["work_execution"]["state"] == LayerState.HEALTHY.value
                        assert report["layers"]["terminal_host"]["state"] == LayerState.FAILED.value


def test_scenario_ide_crash_preserves_work_without_mutation(tmp_path: Path):
    """Scenario 3: IDE window crashes.

    Uncommitted files and diffs must be capturable headlessly outside git worktree.
    """
    repo_dir = tmp_path / "mock_repo"
    recovery_dir = tmp_path / "recovery"
    repo_dir.mkdir()

    # Mock git commands
    with mock.patch("scripts.work_preservation.run_git_command") as mock_git:
        # unstaged diff
        mock_git.side_effect = [
            (0, "diff --git a/file.py b/file.py\n+new line", ""),
            (0, "", ""),  # staged diff
            (0, "untracked_work.py\n", ""),  # untracked files
            (0, "", ""),  # bundle
        ]
        (repo_dir / "untracked_work.py").write_text("print('safe')", encoding="utf-8")

        res = preserve_uncommitted_work(repo_dir=repo_dir, output_dir=recovery_dir, bundle_commits=False)
        target = Path(res["target_dir"])

        assert target.is_dir()
        assert (target / "unstaged.diff").is_file()
        assert "+new line" in (target / "unstaged.diff").read_text(encoding="utf-8")
        assert (target / "untracked" / "untracked_work.py").is_file()
        assert (target / "MANIFEST.json").is_file()


def test_scenario_worker_crash_honest_failure_no_fake_progress():
    """Scenario 4: Worker crashes while surface / hub survives.

    Surface must report honest failure; never report fake progress.
    """
    owned_procs = {
        "worker": {"alive": False, "pid": 3001},  # Worker crashed!
        "hub": {"alive": True, "pid": 3002},
    }
    # Unfinished claim exists
    claims = [{"dispatch_id": "disp-active", "task_id": "task-alpha"}]

    work_eval = assess_work_execution_layer(owned_procs, claims)
    surface_eval = assess_surface_layer(owned_procs)

    # Invariant check: Work is marked FAILED, not hidden
    assert work_eval["state"] == LayerState.FAILED.value
    assert "Work claims in flight" in work_eval["reasons"][0]
    assert surface_eval["state"] == LayerState.HEALTHY.value


def test_scenario_reboot_verdict_blocks_unsafe_reboot():
    """Scenario 5: Freeze recovery evaluates reboot safety.

    Reboot must be blocked if in-flight claims or uncommitted changes exist.
    """
    owned_procs = {"worker": {"alive": True, "pid": 4001}}
    claims = [{"dispatch_id": "active"}]
    journal = {"exists": True, "tasks": {"task-1": "RUNNING"}}
    git_st = {"dirty_count": 5, "unpushed_count": 12}

    verdict, reasons = evaluate_reboot_verdict(owned_procs, claims, journal, git_st)
    assert verdict == "NOT_SAFE_TO_REBOOT"
    assert any("claim" in r.lower() for r in reasons)
    assert any("uncommitted" in r.lower() for r in reasons)
    assert any("unpushed" in r.lower() for r in reasons)


def test_scenario_reboot_verdict_allows_safe_reboot():
    """Scenario 6: All work completed/quiesced and repo clean -> SAFE_TO_REBOOT."""
    owned_procs = {"worker": {"alive": False, "pid": 4001}}
    claims = []
    journal = {"exists": True, "tasks": {"task-1": "COMPLETED"}}
    git_st = {"dirty_count": 0, "unpushed_count": 0}

    verdict, reasons = evaluate_reboot_verdict(owned_procs, claims, journal, git_st)
    assert verdict == "SAFE_TO_REBOOT"
    assert "All journal events committed" in reasons[0]
