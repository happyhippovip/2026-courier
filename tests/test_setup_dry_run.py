"""Unit tests for scripts.setup.dry_run (P6)."""

import json
import pytest
from pathlib import Path

from scripts.setup.dry_run import plan_host_setup, main, SetupPlan


def test_plan_host_setup_fresh_home(tmp_path):
    target = tmp_path / "fresh_courier_home"
    assert not target.exists()

    plan = plan_host_setup(home=target)
    assert plan.target_home == str(target)
    assert plan.is_ready is True
    assert plan.summary["PLANNED"] >= 4  # home + run + logs + delivered_articles
    assert not target.exists()  # Read-only check: directory must NOT be created


def test_plan_host_setup_existing_home_and_subdirs(tmp_path):
    target = tmp_path / "existing_home"
    target.mkdir()
    (target / "run").mkdir()
    (target / "logs").mkdir()
    (target / "delivered_articles").mkdir()
    (target / "run" / "controller.token").write_text("token", encoding="utf-8")

    plan = plan_host_setup(home=target)
    assert plan.summary["SATISFIED"] >= 5
    assert plan.summary["BLOCKED"] == 0
    assert plan.is_ready is True


def test_plan_host_setup_blocks_on_old_python(tmp_path):
    plan = plan_host_setup(home=tmp_path, mock_python_version=(3, 8))
    py_step = next(s for s in plan.steps if s["id"] == "verify_python_version")
    assert py_step["status"] == "BLOCKED"
    assert plan.is_ready is False
    assert plan.summary["BLOCKED"] >= 1


def test_plan_host_setup_blocks_on_missing_git(tmp_path):
    plan = plan_host_setup(home=tmp_path, mock_git_available=False)
    git_step = next(s for s in plan.steps if s["id"] == "check_git_available")
    assert git_step["status"] == "BLOCKED"
    assert plan.is_ready is False


def test_plan_host_setup_blocks_on_unsupported_platform(tmp_path):
    plan = plan_host_setup(home=tmp_path, mock_platform="solaris")
    plat_step = next(s for s in plan.steps if s["id"] == "verify_platform")
    assert plat_step["status"] == "BLOCKED"
    assert plan.is_ready is False


def test_plan_host_setup_is_strictly_read_only(tmp_path):
    target = tmp_path / "never_created"
    before = list(tmp_path.iterdir())

    plan = plan_host_setup(home=target)
    after = list(tmp_path.iterdir())

    assert before == after
    assert not target.exists()


def test_cli_invocation_json_and_text(tmp_path, capsys):
    target = tmp_path / "cli_test_home"

    # JSON output
    ret_json = main(["--home", str(target), "--json"])
    assert ret_json == 0
    captured_json = capsys.readouterr()
    data = json.loads(captured_json.out)
    assert "platform" in data
    assert "steps" in data
    assert data["target_home"] == str(target)

    # Text output
    ret_text = main(["--home", str(target)])
    assert ret_text == 0
    captured_text = capsys.readouterr()
    assert "=== Courier Host Setup Dry-Run ===" in captured_text.out
    assert "Ready to run:   YES" in captured_text.out
