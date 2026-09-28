import pytest
import json
from pathlib import Path

def test_apply_memory_update_proposal_dry_run(tmp_path, monkeypatch):
    import scripts.apply_memory_update_proposal as script
    
    # Mock validate functions to always pass
    monkeypatch.setattr(script, "validate_proposal", lambda d, p: (True, ""))
    monkeypatch.setattr(script, "validate_approval", lambda d, p: (True, ""))
    monkeypatch.setattr(script, "get_memory_commit", lambda r: "commit-123")
    
    monkeypatch.setattr(script, "CANONICAL_MEMORY_ALLOWLIST", {"target.md"})
    
    proposal_file = tmp_path / "prop.json"
    approval_file = tmp_path / "appr.json"
    memory_repo = tmp_path / "mem_repo"
    memory_repo.mkdir()
    
    target_md = memory_repo / "target.md"
    target_md.write_text("# Target\n\nOriginal text.")
    
    proposal_file.write_text(json.dumps({
        "proposal_id": "p-1",
        "source_result_message_id": "msg-1",
        "task_id": "t-1",
        "correlation_id": "c-1",
        "memory_base_commit": "commit-123",
        "target_files": ["target.md"],
        "proposed_changes": [
            {
                "file": "target.md",
                "section": "New Section",
                "status_label": "PLANNED",
                "proposed_text": "Here is the new proposed text."
            }
        ]
    }))
    
    approval_file.write_text(json.dumps({
        "approval_id": "a-1",
        "proposal_id": "p-1",
        "approved_by": "chief",
        "source_result_message_id": "msg-1",
        "task_id": "t-1",
        "correlation_id": "c-1",
        "memory_base_commit": "commit-123"
    }))
    
    result = script.apply_memory_update_proposal(
        proposal_file,
        approval_file,
        memory_repo,
        dry_run=True
    )
    
    assert result["status"] == "DRY_RUN_PASS"
    assert len(result["applied_changes"]) == 1
    assert result["applied_changes"][0]["simulated"] is True
    
    # Since it's a dry run, the file should not have been modified
    assert "New Section" not in target_md.read_text()

def test_apply_memory_update_proposal_mismatch(tmp_path, monkeypatch):
    import scripts.apply_memory_update_proposal as script
    
    monkeypatch.setattr(script, "validate_proposal", lambda d, p: (True, ""))
    monkeypatch.setattr(script, "validate_approval", lambda d, p: (True, ""))
    
    proposal_file = tmp_path / "prop.json"
    approval_file = tmp_path / "appr.json"
    
    proposal_file.write_text(json.dumps({
        "proposal_id": "p-1",
    }))
    
    approval_file.write_text(json.dumps({
        "proposal_id": "p-2",
    }))
    
    with pytest.raises(SystemExit, match="BLOCKED: Approval proposal_id"):
        script.apply_memory_update_proposal(proposal_file, approval_file, tmp_path)

