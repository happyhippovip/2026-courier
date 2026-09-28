import pytest
import json
from pathlib import Path

def test_build_proposal_from_result(tmp_path, monkeypatch):
    import scripts.build_memory_update_proposal as script
    monkeypatch.setattr(script, "get_memory_commit", lambda x: "commit-456")
    monkeypatch.setattr(script, "validate_proposal_against_schema", lambda p, s: (True, ""))
    
    res_path = tmp_path / "result.json"
    res_path.write_text(json.dumps({
        "task_id": "T-123",
        "message_id": "MSG-999",
        "correlation_id": "CORR-01",
        "payload": {
            "verified_facts": ["Test FACT 1", "EXTERNAL FACT 2"],
            "summary": "Completed successfully."
        }
    }))
    
    out_dir = tmp_path / "out"
    proposal = script.build_proposal_from_result(
        result_file=res_path,
        memory_repo_path=tmp_path,
        output_dir=out_dir
    )
    
    assert proposal["task_id"] == "T-123"
    assert proposal["source_result_message_id"] == "MSG-999"

def test_validate_proposal_against_schema():
    import scripts.build_memory_update_proposal as script
    
    proposal = {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-t-1-abcd",
        "source_result_message_id": "msg-1",
        "task_id": "t-1",
        "correlation_id": "c-1",
        "memory_base_commit": "1234567890123456789012345678901234567890",
        "target_files": ["TECHNICAL_CONTEXT.md"],
        "proposed_changes": [
            {
                "file": "TECHNICAL_CONTEXT.md",
                "action": "APPEND",
                "section": "Sec",
                "proposed_text": "text",
                "status_label": "IDEA"
            }
        ],
        "reason": "R",
        "status_labels": ["IDEA"],
        "source_references": ["x"],
        "requires_chief_approval": True,
        "created_at": "2026-09-01T00:00:00Z"
    }
    
    valid, msg = script.validate_proposal_against_schema(proposal, None)
    assert valid is True

