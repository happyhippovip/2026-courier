import pytest
import json
from pathlib import Path

def test_process_proposal_for_chief_decision(tmp_path, monkeypatch):
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
    
    prop_file = tmp_path / "prop.json"
    prop_file.write_text(json.dumps(proposal))
    
    dec_dir = tmp_path / "dec"
    app_dir = tmp_path / "app"
    dec_dir.mkdir()
    app_dir.mkdir()
    
    res = script.process_proposal_for_chief_decision(
        proposal_file=prop_file,
        memory_repo_path=tmp_path,
        output_decisions_dir=dec_dir,
        output_approvals_dir=app_dir
    )
    
    assert res["decision"] == "AUTO_APPROVE"
    assert (dec_dir / "t-1-chief-decision.json").exists()
    assert (app_dir / "t-1-auto-approval.json").exists()

