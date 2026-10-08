import json
import pytest
from pathlib import Path

from scripts.run_antigravity_bridge import (
    check_secrets_in_text,
    AntigravityVisualStateTracker,
    AntigravityHookRunner,
    execute_bridge_task,
    run_chief_review_router,
)


def test_antigravity_secrets_detection_nested(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")

    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    runner = AntigravityHookRunner(tracker)

    # Secret nested deep in dictionary
    nested_payload = {
        "status": "PASS",
        "nested": {
            "auth": {
                "credential": "ghp_SECRETTOKEN12345678901234567890123456"
            }
        }
    }
    with pytest.raises(ValueError, match="Secret detected"):
        runner.on_task_completion(
            task_id="task-sec-1",
            correlation_id="corr-1",
            parent_id=None,
            payload=nested_payload
        )

    # Secret inside list
    list_payload = {
        "items": [
            "benign_item",
            "api_key = 'abcdefghijklmnop12345'"
        ]
    }
    with pytest.raises(ValueError, match="Secret detected"):
        runner.on_task_completion(
            task_id="task-sec-2",
            correlation_id="corr-2",
            parent_id=None,
            payload=list_payload
        )


def test_antigravity_hook_on_failure(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")

    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    runner = AntigravityHookRunner(tracker)

    fail_file = runner.on_task_failure(
        task_id="task-fail-1",
        correlation_id="corr-fail",
        parent_id="parent-0",
        error_message="Host memory pressure exceeded"
    )

    assert fail_file.exists()
    envelope = json.loads(fail_file.read_text(encoding="utf-8"))
    assert envelope["schema_version"] == "2.0"
    assert envelope["type"] == "RESULT"
    assert envelope["status"] == "FAILED"
    assert envelope["source"] == "antigravity"
    assert envelope["destination"] == "courier"
    assert envelope["task_id"] == "task-fail-1"
    assert envelope["payload"]["verdict"] == "FAILED"
    assert envelope["payload"]["error"] == "Host memory pressure exceeded"
    assert len(envelope["payload_hash"]) == 64

    # Tracker state updated to FAILED and blocked
    state_data = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert state_data["state"] == "FAILED"
    assert state_data["blocked"] is True


def test_antigravity_bridge_deduplication_and_force(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(rab, "COURIER_DIR", tmp_path)

    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    runner = AntigravityHookRunner(tracker)

    # Create job file
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps({
        "task_id": "task-dedupe-1",
        "instruction": "First run",
        "allowed_scope": []
    }), encoding="utf-8")

    # First run generates result
    res1 = execute_bridge_task(job_file, runner, force=False)
    data1 = json.loads(res1.read_text(encoding="utf-8"))
    assert data1["payload"]["instruction_summary"] == "First run"

    # Mutate job instruction
    job_file.write_text(json.dumps({
        "task_id": "task-dedupe-1",
        "instruction": "Second run altered",
        "allowed_scope": []
    }), encoding="utf-8")

    # Second run without force returns cached result
    res2 = execute_bridge_task(job_file, runner, force=False)
    data2 = json.loads(res2.read_text(encoding="utf-8"))
    assert data2["payload"]["instruction_summary"] == "First run"

    # Third run with force=True re-executes and updates result
    res3 = execute_bridge_task(job_file, runner, force=True)
    data3 = json.loads(res3.read_text(encoding="utf-8"))
    assert data3["payload"]["instruction_summary"] == "Second run altered"


def test_antigravity_bridge_path_traversal_confinement(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    # Secret file outside repository
    sensitive_file = outside_dir / "secret.txt"
    sensitive_file.write_text("CONFIDENTIAL_SYSTEM_DATA", encoding="utf-8")

    monkeypatch.setattr(rab, "PROCESSED_DIR", repo_root / "processed")
    monkeypatch.setattr(rab, "COURIER_DIR", repo_root)

    tracker = AntigravityVisualStateTracker(repo_dir=repo_root)
    runner = AntigravityHookRunner(tracker)

    # Job attempting path traversal into outside_dir
    job_file = repo_root / "traversal_job.json"
    job_file.write_text(json.dumps({
        "task_id": "task-traversal-1",
        "instruction": "Attempt traversal",
        "allowed_scope": ["../outside/secret.txt"]
    }), encoding="utf-8")

    res = execute_bridge_task(job_file, runner)
    data = json.loads(res.read_text(encoding="utf-8"))

    # Must fall back to EXECUTE_INSTRUCTION without reading the outside file
    assert data["payload"]["action_executed"] == "EXECUTE_INSTRUCTION"
    assert "CONFIDENTIAL_SYSTEM_DATA" not in json.dumps(data)


def test_antigravity_visual_state_tracker_extended(tmp_path):
    tracker = AntigravityVisualStateTracker(agent_id="worker-ag-9", repo_dir=tmp_path)
    state = tracker.update_state(
        state="RUNNING",
        task="task-99",
        progress=0.756,
        position_hint="workstation_kirby",
        workflow="bescheid_review",
        last_action="Parsing legal deadline",
        next_action="Reconciling § 41 VwVfG",
        result={"status": "IN_PROGRESS"},
        blocked=False,
        human_gate="SUPERVISOR_SIGN_OFF"
    )

    assert state["id"] == "worker-ag-9"
    assert state["progress"] == 0.76  # Rounded to 2 decimals
    assert state["position_hint"] == "workstation_kirby"
    assert state["workflow"] == "bescheid_review"
    assert state["human_gate"] == "SUPERVISOR_SIGN_OFF"

    persisted = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert persisted["human_gate"] == "SUPERVISOR_SIGN_OFF"
