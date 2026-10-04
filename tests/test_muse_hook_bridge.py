import pytest
from courier_runtime.muse_hook_bridge import handle_muse_event

def test_session_start():
    result = handle_muse_event("SessionStart", {})
    assert result["courier_event"] == "CourierSessionInit"
    assert result["status"] == "APPROVED"

def test_user_prompt():
    result = handle_muse_event("UserPromptSubmit", {"prompt": "hello"})
    assert result["courier_event"] == "CourierTaskWake"
    assert result["status"] == "APPROVED"

def test_pre_tool_use_mutating():
    result = handle_muse_event("PreToolUse", {"tool_name": "run_command"})
    assert result["courier_event"] == "CourierPreFlightCheck"
    assert result["status"] == "PENDING_POLICY_CHECK"

def test_pre_tool_use_readonly():
    result = handle_muse_event("PreToolUse", {"tool_name": "view_file"})
    assert result["status"] == "IGNORED"

def test_permission_request():
    result = handle_muse_event("PermissionRequest", {})
    assert result["courier_event"] == "CourierApprovalGate"
    assert result["status"] == "REQUIRE_USER"

def test_post_tool_use():
    result = handle_muse_event("PostToolUse", {})
    assert result["courier_event"] == "CourierEvidenceCommit"
    assert result["status"] == "COMMITTED"

def test_post_tool_use_failure():
    result = handle_muse_event("PostToolUseFailure", {"error": "Timeout"})
    assert result["courier_event"] == "CourierEvidenceCommit"
    assert result["status"] == "FAILED"
    assert result["error"] == "Timeout"

def test_unknown_event():
    result = handle_muse_event("UnknownInternalMonologue", {})
    assert result["status"] == "IGNORED"
    assert result["reason"] == "Noisy pass-through"
