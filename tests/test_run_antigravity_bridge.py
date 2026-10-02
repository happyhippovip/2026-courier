import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.run_antigravity_bridge import (
    check_secrets_in_text,
    AntigravityVisualStateTracker,
    AntigravityHookRunner,
    execute_bridge_task,
    run_chief_review_router,
)

def test_check_secrets_in_text():
    assert check_secrets_in_text("No secrets here") == 0
    assert check_secrets_in_text("Here is a token: 'ghp_123456789012345678901234567890123456'") > 0
    assert check_secrets_in_text("sk-abcdefghijklmnopqrstuvwxyz12345678901234") > 0
    assert check_secrets_in_text("api_key = 'abcdef123'") > 0


def test_visual_state_tracker(tmp_path):
    tracker = AntigravityVisualStateTracker(agent_id="test-agent", repo_dir=tmp_path)
    state = tracker.update_state(
        state="RUNNING",
        task="task-123",
        progress=0.5,
        last_action="Testing",
    )
    assert state["state"] == "RUNNING"
    assert state["progress"] == 0.5
    assert state["id"] == "test-agent"
    
    saved_file = tmp_path / "events/agent-states/test-agent.json"
    assert saved_file.exists()
    saved_data = json.loads(saved_file.read_text())
    assert saved_data["state"] == "RUNNING"


def test_antigravity_hook_runner_success(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    runner = AntigravityHookRunner(tracker)
    
    result_file = runner.on_task_completion(
        task_id="task-456",
        correlation_id="corr-1",
        parent_id=None,
        payload={"verdict": "PASS"}
    )
    
    assert result_file.exists()
    data = json.loads(result_file.read_text())
    assert data["type"] == "RESULT"
    assert data["status"] == "COMPLETED"
    assert data["payload"]["verdict"] == "PASS"
    assert data["payload_hash"]


def test_antigravity_hook_runner_secrets_guard(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    runner = AntigravityHookRunner(tracker)
    
    with pytest.raises(ValueError, match="Secret detected"):
        runner.on_task_completion(
            task_id="task-789",
            correlation_id="corr-2",
            parent_id=None,
            payload={"verdict": "PASS", "data": "ghp_123456789012345678901234567890123456"}
        )


def test_execute_bridge_task(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    
    # Create a job file
    job_file = tmp_path / "job.json"
    job_data = {
        "task_id": "task-test-bridge",
        "instruction": "Do something generic",
        "allowed_scope": []
    }
    job_file.write_text(json.dumps(job_data))
    
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    hooks = AntigravityHookRunner(tracker)
    
    result_file = execute_bridge_task(job_file, hooks)
    
    assert result_file.exists()
    result_data = json.loads(result_file.read_text())
    assert result_data["payload"]["verdict"] == "PASS"
    assert result_data["payload"]["action_executed"] == "EXECUTE_INSTRUCTION"


def test_execute_bridge_task_with_fixture(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(rab, "COURIER_DIR", tmp_path)
    
    # Create a fixture file
    fixture_file = tmp_path / "fixture.md"
    fixture_file.write_text("Hello fixture!")
    
    # Create a job file
    job_file = tmp_path / "job.json"
    job_data = {
        "task_id": "task-test-fixture",
        "instruction": "Read fixture",
        "allowed_scope": ["fixture.md"]
    }
    job_file.write_text(json.dumps(job_data))
    
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    hooks = AntigravityHookRunner(tracker)
    
    result_file = execute_bridge_task(job_file, hooks)
    
    assert result_file.exists()
    result_data = json.loads(result_file.read_text())
    assert result_data["payload"]["verdict"] == "PASS"
    assert result_data["payload"]["action_executed"] == "READ_FIXTURE_AND_SUMMARIZE"
    assert "Verified readable content" in result_data["payload"]["content_summary"]


def test_run_chief_review_router(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as rab
    monkeypatch.setattr(rab, "DECISIONS_DIR", tmp_path / "decisions")
    
    # PASS
    result_file_pass = tmp_path / "res1.json"
    result_file_pass.write_text(json.dumps({"payload": {"verdict": "PASS"}}))
    dec1 = run_chief_review_router("t1", result_file_pass)
    assert dec1["verdict"] == "ACCEPTED"
    assert dec1["action"] == "AUTO_APPROVE_SAFE_RESULT"
    
    # NEEDS_FIX
    result_file_fix = tmp_path / "res2.json"
    result_file_fix.write_text(json.dumps({"payload": {"verdict": "NEEDS_FIX"}}))
    dec2 = run_chief_review_router("t2", result_file_fix)
    assert dec2["verdict"] == "NEEDS_FIX"
    assert dec2["action"] == "QUEUE_SCOPED_REPAIR_TASK"
    
    # OTHER -> HUMAN
    result_file_human = tmp_path / "res3.json"
    result_file_human.write_text(json.dumps({"payload": {"verdict": "MAYBE"}}))
    dec3 = run_chief_review_router("t3", result_file_human)
    assert dec3["verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert dec3["action"] == "STOP_AT_HUMAN_GATE"
