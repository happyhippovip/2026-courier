import json
import pytest
from pathlib import Path
from scripts.run_antigravity_bridge import (
    AntigravityVisualStateTracker,
    AntigravityHookRunner,
    execute_bridge_task,
    run_chief_review_router,
    check_secrets_in_text,
    main,
)


@pytest.fixture
def bridge_env(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True)
    return repo_dir


def test_visual_state_tracker(bridge_env):
    tracker = AntigravityVisualStateTracker(repo_dir=bridge_env)
    state = tracker.update_state(
        state="RUNNING",
        task="task-123",
        progress=0.45,
        last_action="Testing action",
    )
    assert state["state"] == "RUNNING"
    assert state["task"] == "task-123"
    assert tracker.state_file.exists()
    saved = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert saved["progress"] == 0.45


def test_hook_runner_lifecycle_and_secret_rejection(bridge_env):
    tracker = AntigravityVisualStateTracker(repo_dir=bridge_env)
    hooks = AntigravityHookRunner(tracker, repo_dir=bridge_env)

    hooks.on_task_start("task-alpha", "corr-1", "Do something useful")
    assert tracker.state_file.exists()

    hooks.on_tool_action("task-alpha", "Sub-action step", 0.5)

    # Secret rejection test
    with pytest.raises(ValueError, match="Secret detected"):
        hooks.on_task_completion(
            task_id="task-alpha",
            correlation_id="corr-1",
            parent_id=None,
            payload={"api_key": "sk-123456789012345678901234567890"},
        )

    # Normal completion
    res_file = hooks.on_task_completion(
        task_id="task-alpha",
        correlation_id="corr-1",
        parent_id=None,
        payload={"verdict": "PASS", "data": "clean content"},
    )
    assert res_file.exists()
    assert (hooks.processed_dir / "task-alpha-result.json").exists()

    # On task stop
    assert hooks.on_task_stop("task-alpha") is True


def test_execute_bridge_task_with_fixture(bridge_env):
    tracker = AntigravityVisualStateTracker(repo_dir=bridge_env)
    hooks = AntigravityHookRunner(tracker, repo_dir=bridge_env)

    # Create a fixture inside bridge_env
    fixture = bridge_env / "sample.json"
    fixture.write_text(json.dumps({"key": "value"}), encoding="utf-8")

    job_data = {
        "task_id": "task-fixture-1",
        "correlation_id": "corr-f1",
        "instruction": "Read the sample fixture",
        "allowed_scope": ["sample.json"],
    }
    job_file = bridge_env / "job.json"
    job_file.write_text(json.dumps(job_data), encoding="utf-8")

    res_file = execute_bridge_task(job_file, hooks, repo_dir=bridge_env)
    assert res_file.exists()

    res_data = json.loads(res_file.read_text(encoding="utf-8"))
    assert res_data["payload"]["verdict"] == "PASS"
    assert res_data["payload"]["action_executed"] == "READ_FIXTURE_AND_SUMMARIZE"
    assert "sample.json" in res_data["payload"]["target_file"]

    # Deduplication test: re-executing without force skips execution
    res_file_dedup = execute_bridge_task(job_file, hooks, force=False, repo_dir=bridge_env)
    assert res_file_dedup == res_file


def test_chief_review_router(bridge_env):
    tracker = AntigravityVisualStateTracker(repo_dir=bridge_env)
    hooks = AntigravityHookRunner(tracker, repo_dir=bridge_env)

    # 1. PASS verdict
    res_pass = hooks.on_task_completion(
        task_id="task-pass",
        correlation_id="corr-p",
        parent_id=None,
        payload={"verdict": "PASS"},
    )
    dec_pass = run_chief_review_router("task-pass", res_pass, repo_dir=bridge_env)
    assert dec_pass["verdict"] == "ACCEPTED"
    assert dec_pass["action"] == "AUTO_APPROVE_SAFE_RESULT"

    # 2. NEEDS_FIX verdict
    res_fix = hooks.on_task_completion(
        task_id="task-fix",
        correlation_id="corr-f",
        parent_id=None,
        payload={"verdict": "NEEDS_FIX"},
    )
    dec_fix = run_chief_review_router("task-fix", res_fix, repo_dir=bridge_env)
    assert dec_fix["verdict"] == "NEEDS_FIX"
    assert dec_fix["action"] == "QUEUE_SCOPED_REPAIR_TASK"


def test_main_cli(bridge_env, capsys):
    # No job found
    code = main(["--repo-dir", str(bridge_env), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "NO_JOB_FOUND"

    # Execute specific job file with review
    job_file = bridge_env / "task-cli-worker-job.json"
    job_file.write_text(json.dumps({
        "task_id": "task-cli-1",
        "correlation_id": "corr-c1",
        "instruction": "Run CLI test",
        "allowed_scope": [],
    }), encoding="utf-8")

    code = main([
        "--job-file", str(job_file),
        "--repo-dir", str(bridge_env),
        "--review",
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "COMPLETED"
    assert data["executed"] is True
    assert data["decision"]["verdict"] == "ACCEPTED"
