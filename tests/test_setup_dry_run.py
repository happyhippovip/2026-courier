"""Unit tests for scripts.setup.dry_run (P6)."""

import json
import pytest
from pathlib import Path

from scripts.setup.dry_run import (
    plan_host_setup,
    main,
    SetupPlan,
    SetupStep,
)


def test_dry_run_never_mutates_filesystem(tmp_path):
    target_dir = tmp_path / "target_install"
    target_dir.mkdir()
    (target_dir / "existing.txt").write_text("DO NOT TOUCH", encoding="utf-8")

    before_entries = list(target_dir.iterdir())

    plan = plan_host_setup(
        target_dir=target_dir,
        os_override="linux",
        env={"COURIER_API_KEY": "dummy-key", "COURIER_VERIFIER_API_KEY": "dummy-verifier"},
    )

    after_entries = list(target_dir.iterdir())
    assert before_entries == after_entries
    assert len(plan.steps) > 0


def test_dry_run_windows_plan(tmp_path):
    plan = plan_host_setup(
        target_dir=tmp_path,
        os_override="windows",
        env={"COURIER_API_KEY": "test-key-win", "COURIER_VERIFIER_API_KEY": "test-vkey-win"},
    )

    assert plan.host_os == "windows"
    assert plan.can_proceed is True
    assert len(plan.missing_prereqs) == 0

    actions = [s.action for s in plan.steps]
    assert "CREATE_DIRECTORY" in actions
    assert "WRITE_CONFIG" in actions
    assert "REGISTER_TASK" in actions

    # Ensure no cleartext credentials in step descriptions
    plan_json = json.dumps(plan.to_dict())
    assert "test-key-win" not in plan_json


def test_dry_run_darwin_plan(tmp_path):
    plan = plan_host_setup(
        target_dir=tmp_path,
        os_override="darwin",
        env={"COURIER_API_KEY": "test-key-mac", "COURIER_VERIFIER_API_KEY": "test-vkey-mac"},
    )

    assert plan.host_os == "darwin"
    assert plan.can_proceed is True
    actions = [s.action for s in plan.steps]
    assert "GENERATE_LAUNCHD_PLIST" in actions
    assert "LOAD_LAUNCHCTL" in actions


def test_dry_run_linux_plan(tmp_path):
    plan = plan_host_setup(
        target_dir=tmp_path,
        os_override="linux",
        env={"COURIER_API_KEY": "test-key-lin", "COURIER_VERIFIER_API_KEY": "test-vkey-lin"},
    )

    assert plan.host_os == "linux"
    assert plan.can_proceed is True
    actions = [s.action for s in plan.steps]
    assert "GENERATE_SYSTEMD_UNIT" in actions
    assert "ENABLE_SYSTEMD_SERVICE" in actions


def test_dry_run_detects_missing_credentials(tmp_path):
    plan = plan_host_setup(
        target_dir=tmp_path,
        os_override="windows",
        env={},  # Empty environment
    )

    assert plan.can_proceed is False
    assert "COURIER_API_KEY" in plan.missing_prereqs
    assert "COURIER_VERIFIER_API_KEY" in plan.missing_prereqs


def test_dry_run_deterministic_sha256(tmp_path):
    env = {"COURIER_API_KEY": "fixed-key", "COURIER_VERIFIER_API_KEY": "fixed-vkey"}
    plan1 = plan_host_setup(target_dir=tmp_path, os_override="linux", env=env)
    plan2 = plan_host_setup(target_dir=tmp_path, os_override="linux", env=env)

    assert plan1.plan_sha256 == plan2.plan_sha256
    assert len(plan1.plan_sha256) == 64


def test_dry_run_cli_invocation(tmp_path, capsys):
    code = main([
        "--target-dir", str(tmp_path),
        "--os", "windows",
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["host_os"] == "windows"
    assert "steps" in data
