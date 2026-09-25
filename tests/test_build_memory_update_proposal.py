import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import build_memory_update_proposal

def test_validate_proposal_against_schema_valid():
    proposal = {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-t1-abc123de",
        "source_result_message_id": "m1",
        "task_id": "t1",
        "correlation_id": "c1",
        "memory_base_commit": "1234567890abcdef1234567890abcdef12345678",
        "target_files": ["f1.md"],
        "proposed_changes": [
            {
                "file": "f1.md",
                "action": "APPEND",
                "section": "sect",
                "proposed_text": "text",
                "status_label": "VERIFIED_CURRENT"
            }
        ],
        "reason": "r1",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["f1.md"],
        "requires_chief_approval": True,
        "created_at": "now"
    }
    
    valid, msg = build_memory_update_proposal.validate_proposal_against_schema(proposal)
    assert valid is True
    assert msg == "VALID"

def test_validate_proposal_against_schema_invalid():
    proposal = {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-t1-abc123de",
        "source_result_message_id": "m1",
        "task_id": "t1",
        "correlation_id": "c1",
        "memory_base_commit": "1234567890abcdef1234567890abcdef12345678",
        "target_files": ["f1.md"],
        "proposed_changes": [
            {
                "file": "f1.md",
                "action": "INVALID_ACTION",
                "section": "sect",
                "proposed_text": "text",
                "status_label": "VERIFIED_CURRENT"
            }
        ],
        "reason": "r1",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["f1.md"],
        "requires_chief_approval": True,
        "created_at": "now"
    }
    
    valid, msg = build_memory_update_proposal.validate_proposal_against_schema(proposal)
    assert valid is False
    assert "invalid action" in msg

def test_build_proposal_from_result(tmp_path):
    res_file = tmp_path / "res.json"
    res_file.write_text(json.dumps({
        "task_id": "t1",
        "message_id": "m1",
        "correlation_id": "c1",
        "payload": {
            "verified_facts": ["fact1 on tiktok", "conflict fact"],
            "summary": "sum"
        }
    }))
    
    out_dir = tmp_path / "out"
    
    with mock.patch("scripts.build_memory_update_proposal.get_memory_commit", return_value="1234567890abcdef1234567890abcdef12345678"):
        proposal = build_memory_update_proposal.build_proposal_from_result(
            result_file=res_file,
            memory_repo_path=tmp_path,
            output_dir=out_dir
        )
        
    assert proposal["task_id"] == "t1"
    assert len(proposal["proposed_changes"]) == 2
    
    labels = proposal["status_labels"]
    assert "EXTERNAL_STATUS" in labels
    assert "CONFLICT" in labels

@mock.patch("scripts.build_memory_update_proposal.build_proposal_from_result")
def test_main_cli(mock_build, tmp_path, capsys):
    res_file = tmp_path / "res.json"
    res_file.write_text("{}")
    
    mock_build.return_value = {
        "proposal_id": "prop-mem-t1-abc123de",
        "task_id": "t1",
        "source_result_message_id": "m1"
    }
    
    with mock.patch.object(sys, 'argv', ['prog', '--result', str(res_file), '--output-dir', str(tmp_path)]):
        build_memory_update_proposal.main()
        
    captured = capsys.readouterr()
    assert "MEMORY_UPDATE_PROPOSAL_CREATED: id=prop-mem-t1-abc123de, task=t1, src_res=m1" in captured.out

