import pytest
import json
import uuid
import datetime
from pathlib import Path
from scripts.apply_memory_update_proposal import (
    apply_memory_update_proposal,
    CANONICAL_MEMORY_ALLOWLIST,
    CANONICAL_STATUS_ALLOWLIST
)

def test_missing_files(tmp_path):
    with pytest.raises(SystemExit):
        apply_memory_update_proposal(tmp_path / "p.json", tmp_path / "a.json")

def test_invalid_json(tmp_path):
    p = tmp_path / "p.json"
    a = tmp_path / "a.json"
    p.write_text("invalid json")
    a.write_text("invalid json")
    with pytest.raises(SystemExit):
        apply_memory_update_proposal(p, a)

def test_mismatch_ids(tmp_path, monkeypatch):
    p = tmp_path / "p.json"
    a = tmp_path / "a.json"
    
    p.write_text(json.dumps({
        "proposal_id": "P1",
        "task_id": "T1",
        "correlation_id": "C1",
        "source_result_message_id": "R1",
        "memory_base_commit": "abcdef",
        "target_files": [],
        "proposed_changes": []
    }))
    
    a.write_text(json.dumps({
        "approval_id": "A1",
        "proposal_id": "P2",  # Mismatch
        "task_id": "T1",
        "correlation_id": "C1",
        "source_result_message_id": "R1",
        "memory_base_commit": "abcdef",
        "approved_by": "chief"
    }))
    
    # mock validate to skip schema checks for this test
    import scripts.apply_memory_update_proposal as module
    monkeypatch.setattr(module, "validate_proposal", lambda x, y: (True, ""))
    monkeypatch.setattr(module, "validate_approval", lambda x, y: (True, ""))
    
    with pytest.raises(SystemExit) as exc:
        apply_memory_update_proposal(p, a, memory_repo_path=tmp_path)
    
    assert "does not match" in str(exc.value)

