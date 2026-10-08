import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.run_codex_bridge import (
    check_secrets_in_text,
    parse_real_codex_result,
    CodexVisualStateTracker,
    CodexHookRunner,
    run_chief_review_router,
    execute_codex_task,
)


def test_check_secrets_in_text_extended():
    # Empty string & benign logs
    assert check_secrets_in_text("") == 0
    assert check_secrets_in_text("normal safe diagnostic text with no secrets") == 0
    assert check_secrets_in_text("uuid: 12345678-1234-1234-1234-123456789abc") == 0
    
    # GitHub personal access tokens
    assert check_secrets_in_text("ghp_012345678901234567890123456789012345") >= 1
    assert check_secrets_in_text("token = 'ghp_ABCDEFGHIJ1234567890abcdefghij'") >= 1
    
    # OpenAI secret tokens
    assert check_secrets_in_text("sk-abcdefghijklmnopqrstuvwxyz0123456789") >= 1

    # Google AIza keys
    assert check_secrets_in_text("AIzaSyD-1234567890abcdefghijklmnopqrstuv") >= 1

    # Generic secret assignments
    assert check_secrets_in_text("api_key = 'abcdefghijklmnop12345'") >= 1
    assert check_secrets_in_text("secret = 'xyz123456789'") >= 1
    assert check_secrets_in_text("bearer: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9") >= 1


def test_parse_real_codex_result_extended():
    # Exactly valid PASS
    res = parse_real_codex_result('{"verdict": "PASS", "summary": "Task complete"}')
    assert res["verdict"] == "PASS"
    assert res["summary"] == "Task complete"

    # Exactly valid HUMAN_APPROVAL_REQUIRED
    res2 = parse_real_codex_result('{"verdict": "HUMAN_APPROVAL_REQUIRED", "summary": "Payment gate"}')
    assert res2["verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert res2["summary"] == "Payment gate"

    # Summary truncation at 500 characters
    long_summary = "A" * 600
    res3 = parse_real_codex_result(json.dumps({"verdict": "PASS", "summary": long_summary}))
    assert len(res3["summary"]) == 500
    assert res3["summary"] == "A" * 500

    # Non-dict inputs raise ValueError
    with pytest.raises(ValueError, match="JSON object"):
        parse_real_codex_result('["PASS", "Summary"]')

    with pytest.raises(ValueError, match="JSON object"):
        parse_real_codex_result('"PASS"')

    with pytest.raises(ValueError, match="JSON object"):
        parse_real_codex_result('12345')

    # Non-string summary raises ValueError
    with pytest.raises(ValueError, match="contract"):
        parse_real_codex_result('{"verdict": "PASS", "summary": 123}')

    # Disallowed verdict raises ValueError
    with pytest.raises(ValueError, match="contract"):
        parse_real_codex_result('{"verdict": "UNVERIFIED", "summary": "Ok"}')


def test_codex_visual_state_tracker_lifecycle(tmp_path):
    tracker = CodexVisualStateTracker(agent_id="test-codex-1", repo_dir=tmp_path)
    
    # Initial / idle update
    state1 = tracker.update_state(state="IDLE", task="none", progress=0.0, last_action="Booting")
    assert state1["state"] == "IDLE"
    assert state1["progress"] == 0.0
    assert state1["id"] == "test-codex-1"

    state_file = tmp_path / "events/agent-states/test-codex-1.json"
    assert state_file.exists()

    # In-progress update
    state2 = tracker.update_state(state="RUNNING", task="task-alpha", progress=0.6, last_action="Refactoring")
    assert state2["state"] == "RUNNING"
    assert state2["progress"] == 0.6
    assert state2["task"] == "task-alpha"

    # Ensure persisted file updates cleanly
    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted["state"] == "RUNNING"
    assert persisted["progress"] == 0.6
    assert persisted["task"] == "task-alpha"


def test_codex_hook_runner_lifecycle_and_secrets(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as rcb
    monkeypatch.setattr(rcb, "PROCESSED_DIR", tmp_path / "processed")

    tracker = CodexVisualStateTracker(agent_id="test-codex-2", repo_dir=tmp_path)
    runner = CodexHookRunner(tracker)

    # on_task_start
    runner.on_task_start(task_id="t-1", correlation_id="c-1", instruction="Execute safe test")
    saved_state = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert saved_state["state"] == "RUNNING"
    assert saved_state["task"] == "t-1"

    # on_tool_action
    runner.on_tool_action(task_id="t-1", action_name="ANALYZE_AST", progress=0.5)
    saved_state = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert saved_state["last_action"] == "ANALYZE_AST"
    assert saved_state["progress"] == 0.5

    # on_task_completion success
    result_path = runner.on_task_completion(
        task_id="t-1",
        correlation_id="c-1",
        parent_id="p-0",
        payload={"verdict": "PASS", "output": "All checks verified clean"}
    )
    assert result_path.exists()
    envelope = json.loads(result_path.read_text(encoding="utf-8"))
    assert envelope["type"] == "RESULT"
    assert envelope["status"] == "COMPLETED"
    assert envelope["source"] == "codex"
    assert envelope["task_id"] == "t-1"
    assert envelope["correlation_id"] == "c-1"
    assert envelope["parent_id"] == "p-0"
    assert envelope["payload"]["verdict"] == "PASS"
    assert len(envelope["payload_hash"]) == 64  # SHA-256

    saved_state = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert saved_state["state"] == "AWAITING_CHIEF_REVIEW"

    # on_task_completion with secret leaks fails closed
    with pytest.raises(ValueError, match="Secret detected"):
        runner.on_task_completion(
            task_id="t-2",
            correlation_id="c-2",
            parent_id=None,
            payload={"verdict": "PASS", "leaked": "ghp_SECRETTOKEN12345678901234567890123456"}
        )

    # on_task_failure emits FAILED result
    fail_path = runner.on_task_failure(
        task_id="t-3",
        correlation_id="c-3",
        parent_id=None,
        error_message="Subprocess timed out after 30s"
    )
    assert fail_path.exists()
    fail_envelope = json.loads(fail_path.read_text(encoding="utf-8"))
    assert fail_envelope["type"] == "RESULT"
    assert fail_envelope["status"] == "FAILED"
    assert fail_envelope["payload"]["error"] == "Subprocess timed out after 30s"

    saved_state = json.loads(tracker.state_file.read_text(encoding="utf-8"))
    assert saved_state["state"] == "FAILED"

    # on_task_stop verifies result file existence
    assert runner.on_task_stop("t-1") is True
    assert runner.on_task_stop("t-nonexistent") is False


def test_run_chief_review_router_verdicts(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as rcb
    monkeypatch.setattr(rcb, "DECISIONS_DIR", tmp_path / "decisions")

    # 1. PASS -> ACCEPTED
    res_pass = tmp_path / "res_pass.json"
    res_pass.write_text(json.dumps({"payload": {"verdict": "PASS", "summary": "Done"}}), encoding="utf-8")
    d1 = run_chief_review_router("task-pass", res_pass)
    assert d1["verdict"] == "ACCEPTED"
    assert d1["action"] == "AUTO_APPROVE_SAFE_RESULT"
    assert (tmp_path / "decisions/task-pass-chief-decision.json").exists()

    # 2. HUMAN_APPROVAL_REQUIRED -> STOP_AT_HUMAN_GATE
    res_human = tmp_path / "res_human.json"
    res_human.write_text(json.dumps({"payload": {"verdict": "HUMAN_APPROVAL_REQUIRED", "summary": "Wait for boss"}}), encoding="utf-8")
    d2 = run_chief_review_router("task-human", res_human)
    assert d2["verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert d2["action"] == "STOP_AT_HUMAN_GATE"
    assert (tmp_path / "decisions/task-human-chief-decision.json").exists()

    # 3. NEEDS_FIX / FAILED -> QUEUE_SCOPED_REPAIR_TASK
    res_fix = tmp_path / "res_fix.json"
    res_fix.write_text(json.dumps({"payload": {"verdict": "NEEDS_FIX", "summary": "Broken syntax"}}), encoding="utf-8")
    d3 = run_chief_review_router("task-fix", res_fix)
    assert d3["verdict"] == "NEEDS_FIX"
    assert d3["action"] == "QUEUE_SCOPED_REPAIR_TASK"
    assert (tmp_path / "decisions/task-fix-chief-decision.json").exists()
