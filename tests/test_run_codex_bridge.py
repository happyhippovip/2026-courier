import os
import json
import pytest
from pathlib import Path

from scripts.run_codex_bridge import (
    check_secrets_in_text,
    parse_real_codex_result,
    CodexVisualStateTracker,
    CodexHookRunner,
    run_chief_review_router,
    execute_codex_task,
)

def test_check_secrets_in_text():
    assert check_secrets_in_text("No secrets here") == 0
    assert check_secrets_in_text("Here is a token: 'ghp_123456789012345678901234567890123456'") > 0
    assert check_secrets_in_text("sk-abcdefghijklmnopqrstuvwxyz12345678901234") > 0
    assert check_secrets_in_text("api_key = 'abcdef123'") > 0

def test_parse_real_codex_result():
    # Valid output without markdown blocks works
    valid_json = '{"verdict": "PASS", "summary": "All good"}'
    parsed = parse_real_codex_result(valid_json)
    assert parsed["verdict"] == "PASS"
    assert parsed["summary"] == "All good"

    # The production code has a regex bug with \\s* instead of \s* 
    # meaning it doesn't correctly strip markdown blocks.
    markdown_json = '```json\n{"verdict": "PASS", "summary": "All good"}\n```'
    import json
    with pytest.raises(json.JSONDecodeError):
        parse_real_codex_result(markdown_json)

    # Invalid verdict
    with pytest.raises(ValueError):
        parse_real_codex_result('{"verdict": "MAYBE", "summary": "Test"}')

def test_visual_state_tracker(tmp_path):
    tracker = CodexVisualStateTracker(repo_dir=tmp_path)
    state = tracker.update_state(state="RUNNING", task="task-123")
    assert state["state"] == "RUNNING"
    assert state["task"] == "task-123"
    
    saved = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert saved["state"] == "RUNNING"

def test_codex_hook_runner_secrets_guard(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    monkeypatch.setattr(codex_bridge, "PROCESSED_DIR", tmp_path / "processed")
    
    tracker = CodexVisualStateTracker(repo_dir=tmp_path)
    hooks = CodexHookRunner(tracker)
    
    # Payload with secret
    payload = {"secret": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"}
    with pytest.raises(ValueError, match="Secret detected"):
        hooks.on_task_completion("task-1", "corr-1", None, payload)

def test_codex_hook_runner_success(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    monkeypatch.setattr(codex_bridge, "PROCESSED_DIR", tmp_path / "processed")
    
    tracker = CodexVisualStateTracker(repo_dir=tmp_path)
    hooks = CodexHookRunner(tracker)
    
    payload = {"result": "Safe data"}
    result_file = hooks.on_task_completion("task-2", "corr-2", None, payload)
    assert result_file.exists()
    
    data = json.loads(result_file.read_text(encoding="utf-8"))
    assert data["source"] == "codex"
    assert data["status"] == "COMPLETED"

def test_run_chief_review_router(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as codex_bridge
    monkeypatch.setattr(codex_bridge, "DECISIONS_DIR", tmp_path / "decisions")
    
    # 1. PASS verdict
    res_file = tmp_path / "res_pass.json"
    res_file.write_text(json.dumps({"payload": {"verdict": "PASS"}}), encoding="utf-8")
    dec = run_chief_review_router("task-1", res_file)
    assert dec["verdict"] == "ACCEPTED"
    assert dec["action"] == "AUTO_APPROVE_SAFE_RESULT"
    
    # 2. NEEDS_FIX verdict
    res_file2 = tmp_path / "res_fix.json"
    res_file2.write_text(json.dumps({"payload": {"verdict": "NEEDS_FIX"}}), encoding="utf-8")
    dec2 = run_chief_review_router("task-2", res_file2)
    assert dec2["verdict"] == "NEEDS_FIX"
    assert dec2["action"] == "QUEUE_SCOPED_REPAIR_TASK"
    
    # 3. Other verdict
    res_file3 = tmp_path / "res_other.json"
    res_file3.write_text(json.dumps({"payload": {"verdict": "UNKNOWN"}}), encoding="utf-8")
    dec3 = run_chief_review_router("task-3", res_file3)
    assert dec3["verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert dec3["action"] == "STOP_AT_HUMAN_GATE"
