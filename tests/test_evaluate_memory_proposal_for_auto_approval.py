import pytest
import json
from pathlib import Path

def test_evaluate_proposal_auto_approve(monkeypatch):
    import scripts.evaluate_memory_proposal_for_auto_approval as script
    monkeypatch.setattr(script, "get_memory_commit", lambda x: "commit-123")
    monkeypatch.setattr(script, "CANONICAL_MEMORY_ALLOWLIST", {"test.md"})
    monkeypatch.setattr(script, "CANONICAL_STATUS_ALLOWLIST", {"VERIFIED_CURRENT"})
    
    proposal = {
        "schema_version": "2.0",
        "proposal_id": "p-1",
        "source_result_message_id": "msg-1",
        "task_id": "t-1",
        "correlation_id": "c-1",
        "memory_base_commit": "commit-123",
        "target_files": ["test.md"],
        "proposed_changes": [
            {
                "file": "test.md",
                "action": "APPEND",
                "proposed_text": "safe text",
                "status_label": "VERIFIED_CURRENT"
            }
        ],
        "reason": "Update",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["http://test"],
        "requires_chief_approval": True,
        "created_at": "2026-09-01T00:00:00Z"
    }
    
    decision, reason, labels = script.evaluate_proposal(proposal, Path("dummy"))
    assert decision == "AUTO_APPROVE"

def test_evaluate_proposal_human_review(monkeypatch):
    import scripts.evaluate_memory_proposal_for_auto_approval as script
    monkeypatch.setattr(script, "get_memory_commit", lambda x: "commit-123")
    monkeypatch.setattr(script, "CANONICAL_MEMORY_ALLOWLIST", {"test.md"})
    monkeypatch.setattr(script, "CANONICAL_STATUS_ALLOWLIST", {"VERIFIED_CURRENT", "IDEA"})
    
    proposal = {
        "schema_version": "2.0",
        "proposal_id": "p-1",
        "source_result_message_id": "msg-1",
        "task_id": "t-1",
        "correlation_id": "c-1",
        "memory_base_commit": "commit-123",
        "target_files": ["test.md"],
        "proposed_changes": [
            {
                "file": "test.md",
                "action": "APPEND",
                "proposed_text": "safe text",
                "status_label": "IDEA"
            }
        ],
        "reason": "Update",
        "status_labels": ["IDEA"],
        "source_references": ["http://test"],
        "requires_chief_approval": True,
        "created_at": "2026-09-01T00:00:00Z"
    }
    
    decision, reason, labels = script.evaluate_proposal(proposal, Path("dummy"))
    assert decision == "HUMAN_REVIEW"
    assert "STRATEGIC_CHANGE" in reason

def test_evaluate_proposal_blocked_secrets(monkeypatch):
    import scripts.evaluate_memory_proposal_for_auto_approval as script
    monkeypatch.setattr(script, "get_memory_commit", lambda x: "commit-123")
    monkeypatch.setattr(script, "CANONICAL_MEMORY_ALLOWLIST", {"test.md"})
    monkeypatch.setattr(script, "CANONICAL_STATUS_ALLOWLIST", {"VERIFIED_CURRENT"})
    
    proposal = {
        "schema_version": "2.0",
        "proposal_id": "p-1",
        "source_result_message_id": "msg-1",
        "task_id": "t-1",
        "correlation_id": "c-1",
        "memory_base_commit": "commit-123",
        "target_files": ["test.md"],
        "proposed_changes": [
            {
                "file": "test.md",
                "action": "APPEND",
                "proposed_text": "password='SuperSecretPassword123'",
                "status_label": "VERIFIED_CURRENT"
            }
        ],
        "reason": "Update",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["http://test"],
        "requires_chief_approval": True,
        "created_at": "2026-09-01T00:00:00Z"
    }
    
    decision, reason, labels = script.evaluate_proposal(proposal, Path("dummy"))
    assert decision == "BLOCKED"
    assert "SECRET_DETECTED" in reason

