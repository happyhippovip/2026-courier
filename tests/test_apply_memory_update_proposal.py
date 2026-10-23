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
    apply_memory_update_proposal,
    main,
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
def test_apply_does_not_follow_a_symlink(mock_get_commit, tmp_path, base_proposal, base_approval, mock_schemas):
    prop_schema, appr_schema = mock_schemas
    mock_get_commit.return_value = base_proposal["memory_base_commit"]
    prop_file = tmp_path / "proposal.json"
    prop_file.write_text(json.dumps(base_proposal), encoding="utf-8")
    appr_file = tmp_path / "approval.json"
    appr_file.write_text(json.dumps(base_approval), encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("## Overview\nkeep\n", encoding="utf-8")
    memory_repo = tmp_path / "memory"
    memory_repo.mkdir()
    state_file = memory_repo / "PROJECT_STATE.md"
    state_file.symlink_to(outside)
    try:
        result = apply_memory_update_proposal(
            prop_file, appr_file, memory_repo, dry_run=False,
            proposal_schema_path=prop_schema, approval_schema_path=appr_schema,
        )
    except SystemExit as exc:
        outcome = str(exc)
    else:
        outcome = result.get("status")
    assert outcome == "MEMORY_WRITE_HANDLER_ERROR: refusing to follow a symlink" and outside.read_text(encoding="utf-8") == "## Overview\nkeep\n" and state_file.is_symlink(), (
        outcome, outside.read_text(encoding="utf-8"), state_file.is_symlink(),
    )

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


@patch("scripts.apply_memory_update_proposal.get_memory_commit")
def test_cli_memory_repo_does_not_follow_a_symlink(mock_get_commit, tmp_path, base_proposal, base_approval, mock_schemas):
    prop_schema, appr_schema = mock_schemas
    mock_get_commit.return_value = base_proposal["memory_base_commit"]
    prop_file = tmp_path / "proposal.json"
    prop_file.write_text(json.dumps(base_proposal), encoding="utf-8")
    appr_file = tmp_path / "approval.json"
    appr_file.write_text(json.dumps(base_approval), encoding="utf-8")

    def run(mem: Path):
        argv = [
            "prog",
            "--proposal", str(prop_file),
            "--approval", str(appr_file),
            "--memory-repo", str(mem),
            "--proposal-schema", str(prop_schema),
            "--approval-schema", str(appr_schema),
        ]
        with patch.object(sys, "argv", argv):
            try:
                main()
                err = None
            except SystemExit as exc:
                err = str(exc)
        return err

    real = tmp_path / "real-memory"
    real.mkdir()
    state = real / "PROJECT_STATE.md"
    state.write_text("## Overview\nkeep\n", encoding="utf-8")
    linked = tmp_path / "linked-memory"
    linked.symlink_to(real)

    parent_real = tmp_path / "parent-real"
    nested = parent_real / "repo"
    nested.mkdir(parents=True)
    nested_state = nested / "PROJECT_STATE.md"
    nested_state.write_text("## Overview\nkeep\n", encoding="utf-8")
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(parent_real)

    plain = tmp_path / "plain-memory"
    plain.mkdir()
    plain_state = plain / "PROJECT_STATE.md"
    plain_state.write_text("## Overview\nkeep\n", encoding="utf-8")

    err_link = run(linked)
    err_parent = run(parent_link / "repo")
    err_plain = run(plain)
    refused = "MEMORY_WRITE_HANDLER_ERROR: refusing to follow a symlink"
    assert (
        err_link == refused
        and state.read_text(encoding="utf-8") == "## Overview\nkeep\n"
        and err_parent == refused
        and nested_state.read_text(encoding="utf-8") == "## Overview\nkeep\n"
        and err_plain is None
        and "New state." in plain_state.read_text(encoding="utf-8")
        and linked.is_symlink()
        and parent_link.is_symlink()
    ), (
        err_link, state.read_text(encoding="utf-8"),
        err_parent, nested_state.read_text(encoding="utf-8"),
        err_plain, plain_state.read_text(encoding="utf-8"),
    )


@patch("scripts.apply_memory_update_proposal.get_memory_commit")
def test_proposal_and_approval_do_not_follow_a_symlink(mock_get_commit, tmp_path, base_proposal, base_approval, mock_schemas):
    prop_schema, appr_schema = mock_schemas
    mock_get_commit.return_value = base_proposal["memory_base_commit"]

    def memory(name):
        repo = tmp_path / name
        repo.mkdir()
        state = repo / "PROJECT_STATE.md"
        state.write_text("## Overview\nkeep\n", encoding="utf-8")
        return repo, state

    def run_main(prop, appr, repo):
        argv = [
            "prog",
            "--proposal", str(prop),
            "--approval", str(appr),
            "--memory-repo", str(repo),
            "--proposal-schema", str(prop_schema),
            "--approval-schema", str(appr_schema),
        ]
        with patch.object(sys, "argv", argv):
            try:
                main()
                return None
            except SystemExit as exc:
                return str(exc)

    secret = json.loads(json.dumps(base_proposal))
    secret["proposed_changes"][0]["proposed_text"] = "SECRET-APPLY-BODY"
    outside_prop = tmp_path / "outside-prop.json"
    outside_prop.write_text(json.dumps(secret), encoding="utf-8")
    linked_prop = tmp_path / "linked-prop.json"
    linked_prop.symlink_to(outside_prop)
    appr_file = tmp_path / "approval.json"
    appr_file.write_text(json.dumps(base_approval), encoding="utf-8")
    repo_prop, state_prop = memory("mem-prop")
    err_prop = run_main(linked_prop, appr_file, repo_prop)

    real_prop = tmp_path / "proposal.json"
    real_prop.write_text(json.dumps(base_proposal), encoding="utf-8")
    outside_appr = tmp_path / "outside-appr.json"
    outside_appr.write_text(json.dumps(base_approval), encoding="utf-8")
    linked_appr = tmp_path / "linked-appr.json"
    linked_appr.symlink_to(outside_appr)
    repo_appr, state_appr = memory("mem-appr")
    err_appr = run_main(real_prop, linked_appr, repo_appr)

    repo_lib, state_lib = memory("mem-lib")
    try:
        apply_memory_update_proposal(
            linked_prop, appr_file, repo_lib, dry_run=False,
            proposal_schema_path=prop_schema, approval_schema_path=appr_schema,
        )
        err_lib = None
    except SystemExit as exc:
        err_lib = str(exc)

    kept = "## Overview\nkeep\n"
    refused = "MEMORY_WRITE_HANDLER_ERROR: refusing to follow a symlink"
    assert (
        err_prop == refused
        and state_prop.read_text(encoding="utf-8") == kept
        and err_appr == refused
        and state_appr.read_text(encoding="utf-8") == kept
        and err_lib == refused
        and state_lib.read_text(encoding="utf-8") == kept
        and linked_prop.is_symlink()
        and linked_appr.is_symlink()
    ), (
        err_prop, state_prop.read_text(encoding="utf-8"),
        err_appr, state_appr.read_text(encoding="utf-8"),
        err_lib, state_lib.read_text(encoding="utf-8"),
    )
