"""
Courier implementation of the Muse Hook Bridge mapping (M06).
Maps Muse lifecycle events to Courier events for durable ledgering and safety.
"""

from typing import Dict, Any

def handle_muse_event(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main interceptor for Muse hooks.
    Routes Muse events to their Courier equivalents based on M06 constraints.
    """
    handlers = {
        "SessionStart": _handle_session_start,
        "UserPromptSubmit": _handle_user_prompt,
        "PreToolUse": _handle_pre_tool_use,
        "PermissionRequest": _handle_permission_request,
        "PostToolUse": _handle_post_tool_use,
        "PostToolUseFailure": _handle_post_tool_use_failure,
        "SubagentStart": _handle_subagent_start,
        "SubagentStop": _handle_subagent_stop,
        "Stop": _handle_stop,
        "SessionEnd": _handle_session_end,
    }
    
    if event_type in handlers:
        return handlers[event_type](payload)
    return {"status": "IGNORED", "reason": "Noisy pass-through"}

def _handle_session_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierSessionInit", "action": "allocate_session", "status": "APPROVED"}

def _handle_user_prompt(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierTaskWake", "action": "hash_prompt_for_ledger", "status": "APPROVED"}

def _handle_pre_tool_use(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = payload.get("tool_name", "")
    if tool_name in ["run_command", "write_to_file", "replace_file_content", "multi_replace_file_content"]:
        return {"courier_event": "CourierPreFlightCheck", "status": "PENDING_POLICY_CHECK"}
    return {"status": "IGNORED", "reason": "Read-only tool"}

def _handle_permission_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierApprovalGate", "status": "REQUIRE_USER"}

def _handle_post_tool_use(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierEvidenceCommit", "status": "COMMITTED"}

def _handle_post_tool_use_failure(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierEvidenceCommit", "status": "FAILED", "error": payload.get("error")}

def _handle_subagent_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierSubTaskDelegation", "action": "claim_slot"}

def _handle_subagent_stop(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierSubTaskDelegation", "action": "release_slot"}

def _handle_stop(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierLeaseRelease", "action": "persist_checkpoint"}

def _handle_session_end(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"courier_event": "CourierLeaseRelease", "action": "persist_checkpoint"}
