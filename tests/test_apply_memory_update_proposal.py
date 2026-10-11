import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.apply_memory_update_proposal import (
    validate_proposal,
    validate_approval,
    check_secret_guard,
    apply_memory_update_proposal
)

@pytest.fixture
def mock_schemas(tmp_path):
    prop_schema = tmp_path / "prop.schema.json"
    prop_schema.write_text("{}")
    appr_schema = tmp_path / "appr.schema.json"
    appr_schema.write_text("{}")
    return prop_schema, appr_schema

@pytest.fixture
def base_proposal():
    return {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-123",
        "source_result_message_id": "msg-1",
        "task_id": "task-1",
        "correlation_id": "corr-1",
        "memory_base_commit": "abcdef1234567890abcdef1234567890abcdef12",
        "target_files": ["PROJECT_STATE.md"],
        "proposed_changes": [
            {
                "file": "PROJECT_STATE.md",
                "section": "Overview",
                "action": "APPEND",
                "status_label": "VERIFIED_CURRENT",
                "proposed_text": "New state."
            }
        ],
        "reason": "Update state",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": [],
        "requires_chief_approval": True,
        "created_at": "2026-01-01T00:00:00Z"
    }

@pytest.fixture
def base_approval():
    return {
        "schema_version": "2.0",
        "approval_id": "appr-mem-123",
        "proposal_id": "prop-mem-123",
        "source_result_message_id": "msg-1",
        "task_id": "task-1",
        "correlation_id": "corr-1",
        "memory_base_commit": "abcdef1234567890abcdef1234567890abcdef12",
        "approved_by": "CHIEF",
        "approval_status": "APPROVED",
        "approved_at": "2026-01-01T00:05:00Z"
    }

def test_validate_proposal_success(base_proposal, mock_schemas):
    prop_schema, _ = mock_schemas
    valid, err = validate_proposal(base_proposal, prop_schema)
    assert valid is True

def test_validate_proposal_missing_field(base_proposal, mock_schemas):
    prop_schema, _ = mock_schemas
    del base_proposal["schema_version"]
    valid, err = validate_proposal(base_proposal, prop_schema)
    assert valid is False
    assert "Proposal field mismatch" in err

def test_validate_approval_success(base_approval, mock_schemas):
    _, appr_schema = mock_schemas
    valid, err = validate_approval(base_approval, appr_schema)
    assert valid is True

def test_check_secret_guard():
    assert check_secret_guard("Here is my token: ghp_123456789012345678901234567890") is True
    assert check_secret_guard("No secrets here") is False
    assert check_secret_guard("API_KEY = 'secret123'") is True

@patch("scripts.apply_memory_update_proposal.get_memory_commit")
def test_apply_memory_update_proposal_success(mock_get_commit, tmp_path, base_proposal, base_approval, mock_schemas):
    prop_schema, appr_schema = mock_schemas
    
    mock_get_commit.return_value = base_proposal["memory_base_commit"]
    
    prop_file = tmp_path / "proposal.json"
    prop_file.write_text(json.dumps(base_proposal))
    
    appr_file = tmp_path / "approval.json"
    appr_file.write_text(json.dumps(base_approval))
    
    memory_repo = tmp_path / "memory"
    memory_repo.mkdir()
    state_file = memory_repo / "PROJECT_STATE.md"
    state_file.write_text("## Overview\nOld state.")
    
    result = apply_memory_update_proposal(
        prop_file, appr_file, memory_repo, dry_run=False,
        proposal_schema_path=prop_schema, approval_schema_path=appr_schema
    )
    
    assert result["status"] == "APPLIED_PASS"
    assert "New state." in state_file.read_text()

@patch("scripts.apply_memory_update_proposal.get_memory_commit")
def test_apply_memory_update_proposal_mismatch(mock_get_commit, tmp_path, base_proposal, base_approval, mock_schemas):
    prop_schema, appr_schema = mock_schemas
    
    # Intentionally mismatch correlation_id
    base_approval["correlation_id"] = "wrong-corr"
    
    prop_file = tmp_path / "proposal.json"
    prop_file.write_text(json.dumps(base_proposal))
    
    appr_file = tmp_path / "approval.json"
    appr_file.write_text(json.dumps(base_approval))
    
    memory_repo = tmp_path / "memory"
    memory_repo.mkdir()
    
    with pytest.raises(SystemExit) as exc:
        apply_memory_update_proposal(
            prop_file, appr_file, memory_repo, dry_run=False,
            proposal_schema_path=prop_schema, approval_schema_path=appr_schema
        )
    
    assert "BLOCKED: Approval correlation_id" in str(exc.value)

@patch("scripts.apply_memory_update_proposal.get_memory_commit")
def test_apply_memory_update_proposal_secret(mock_get_commit, tmp_path, base_proposal, base_approval, mock_schemas):
    prop_schema, appr_schema = mock_schemas
    
    mock_get_commit.return_value = base_proposal["memory_base_commit"]
    
    base_proposal["proposed_changes"][0]["proposed_text"] = "token: ghp_123456789012345678901234567890"
    
    prop_file = tmp_path / "proposal.json"
    prop_file.write_text(json.dumps(base_proposal))
    
    appr_file = tmp_path / "approval.json"
    appr_file.write_text(json.dumps(base_approval))
    
    memory_repo = tmp_path / "memory"
    memory_repo.mkdir()
    
    with pytest.raises(SystemExit) as exc:
        apply_memory_update_proposal(
            prop_file, appr_file, memory_repo, dry_run=False,
            proposal_schema_path=prop_schema, approval_schema_path=appr_schema
        )
        
    assert "sensitive credential/secret pattern" in str(exc.value)
