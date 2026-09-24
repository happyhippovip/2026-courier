import json
import subprocess
import sys
from pathlib import Path
import pytest

from scripts.apply_memory_update_proposal import (
    apply_memory_update_proposal,
    get_memory_commit,
    MemoryApplyError,
    main,
)


@pytest.fixture
def mock_memory_repo(tmp_path: Path):
    repo_dir = tmp_path / "memory_repo"
    repo_dir.mkdir()
    git_dir = repo_dir / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("1111222233334444555566667777888899990000", encoding="utf-8")

    # Target markdown file
    target_file = repo_dir / "PROJECT_STATE.md"
    target_file.write_text("# Project State\n\n## Overview\nInitial content\n", encoding="utf-8")

    return repo_dir


def test_get_memory_commit(mock_memory_repo: Path):
    commit = get_memory_commit(mock_memory_repo)
    assert commit == "1111222233334444555566667777888899990000"


def test_apply_proposal_dry_run_and_real_write(tmp_path: Path, mock_memory_repo: Path):
    commit = get_memory_commit(mock_memory_repo)

    proposal = {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-test-01",
        "source_result_message_id": "msg-001",
        "task_id": "task-001",
        "correlation_id": "corr-001",
        "memory_base_commit": commit,
        "target_files": ["PROJECT_STATE.md"],
        "proposed_changes": [
            {
                "file": "PROJECT_STATE.md",
                "section": "Windows Verification",
                "action": "APPEND",
                "status_label": "VERIFIED_CURRENT",
                "proposed_text": "Windows verification successfully completed."
            }
        ],
        "reason": "Test memory update",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["ref-1"],
        "requires_chief_approval": True,
        "created_at": "2026-09-24T12:00:00Z"
    }

    approval = {
        "schema_version": "2.0",
        "approval_id": "appr-mem-test-01",
        "proposal_id": "prop-mem-test-01",
        "source_result_message_id": "msg-001",
        "task_id": "task-001",
        "correlation_id": "corr-001",
        "memory_base_commit": commit,
        "approved_by": "chief",
        "approval_status": "APPROVED",
        "approved_at": "2026-09-24T12:05:00Z"
    }

    prop_file = tmp_path / "prop.json"
    appr_file = tmp_path / "appr.json"
    prop_file.write_text(json.dumps(proposal), encoding="utf-8")
    appr_file.write_text(json.dumps(approval), encoding="utf-8")

    # 1. Dry run
    dry_res = apply_memory_update_proposal(
        prop_file,
        appr_file,
        memory_repo_path=mock_memory_repo,
        dry_run=True,
    )
    assert dry_res["status"] == "DRY_RUN_PASS"
    target_file = mock_memory_repo / "PROJECT_STATE.md"
    assert "Windows verification successfully completed." not in target_file.read_text(encoding="utf-8")

    # 2. Real application
    real_res = apply_memory_update_proposal(
        prop_file,
        appr_file,
        memory_repo_path=mock_memory_repo,
        dry_run=False,
    )
    assert real_res["status"] == "APPLIED_PASS"
    assert "Windows verification successfully completed." in target_file.read_text(encoding="utf-8")


def test_apply_proposal_conflict_rejection(tmp_path: Path, mock_memory_repo: Path):
    proposal = {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-test-02",
        "source_result_message_id": "msg-002",
        "task_id": "task-002",
        "correlation_id": "corr-002",
        "memory_base_commit": "0000000000000000000000000000000000000000",
        "target_files": ["PROJECT_STATE.md"],
        "proposed_changes": [
            {
                "file": "PROJECT_STATE.md",
                "section": "Overview",
                "action": "APPEND",
                "status_label": "VERIFIED_CURRENT",
                "proposed_text": "Conflicting text."
            }
        ],
        "reason": "Test conflict",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["ref-2"],
        "requires_chief_approval": True,
        "created_at": "2026-09-24T12:00:00Z"
    }

    approval = {
        "schema_version": "2.0",
        "approval_id": "appr-mem-test-02",
        "proposal_id": "prop-mem-test-02",
        "source_result_message_id": "msg-002",
        "task_id": "task-002",
        "correlation_id": "corr-002",
        "memory_base_commit": "0000000000000000000000000000000000000000",
        "approved_by": "chief",
        "approval_status": "APPROVED",
        "approved_at": "2026-09-24T12:05:00Z"
    }

    prop_file = tmp_path / "prop.json"
    appr_file = tmp_path / "appr.json"
    prop_file.write_text(json.dumps(proposal), encoding="utf-8")
    appr_file.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(MemoryApplyError, match="CONFLICT: Current memory HEAD commit"):
        apply_memory_update_proposal(
            prop_file,
            appr_file,
            memory_repo_path=mock_memory_repo,
            dry_run=True,
        )


def test_apply_proposal_secret_rejection(tmp_path: Path, mock_memory_repo: Path):
    commit = get_memory_commit(mock_memory_repo)

    proposal = {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-test-03",
        "source_result_message_id": "msg-003",
        "task_id": "task-003",
        "correlation_id": "corr-003",
        "memory_base_commit": commit,
        "target_files": ["PROJECT_STATE.md"],
        "proposed_changes": [
            {
                "file": "PROJECT_STATE.md",
                "section": "Overview",
                "action": "APPEND",
                "status_label": "VERIFIED_CURRENT",
                "proposed_text": "api_key = 'sk-1234567890abcdef12345678'"
            }
        ],
        "reason": "Test secret leakage",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["ref-3"],
        "requires_chief_approval": True,
        "created_at": "2026-09-24T12:00:00Z"
    }

    approval = {
        "schema_version": "2.0",
        "approval_id": "appr-mem-test-03",
        "proposal_id": "prop-mem-test-03",
        "source_result_message_id": "msg-003",
        "task_id": "task-003",
        "correlation_id": "corr-003",
        "memory_base_commit": commit,
        "approved_by": "chief",
        "approval_status": "APPROVED",
        "approved_at": "2026-09-24T12:05:00Z"
    }

    prop_file = tmp_path / "prop.json"
    appr_file = tmp_path / "appr.json"
    prop_file.write_text(json.dumps(proposal), encoding="utf-8")
    appr_file.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(MemoryApplyError, match="contains sensitive credential/secret pattern"):
        apply_memory_update_proposal(
            prop_file,
            appr_file,
            memory_repo_path=mock_memory_repo,
            dry_run=True,
        )


def test_apply_proposal_cli(tmp_path: Path, mock_memory_repo: Path, capsys):
    commit = get_memory_commit(mock_memory_repo)

    proposal = {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-test-04",
        "source_result_message_id": "msg-004",
        "task_id": "task-004",
        "correlation_id": "corr-004",
        "memory_base_commit": commit,
        "target_files": ["PROJECT_STATE.md"],
        "proposed_changes": [
            {
                "file": "PROJECT_STATE.md",
                "section": "CLI Test",
                "action": "APPEND",
                "status_label": "VERIFIED_CURRENT",
                "proposed_text": "CLI test entry."
            }
        ],
        "reason": "Test CLI",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["ref-4"],
        "requires_chief_approval": True,
        "created_at": "2026-09-24T12:00:00Z"
    }

    approval = {
        "schema_version": "2.0",
        "approval_id": "appr-mem-test-04",
        "proposal_id": "prop-mem-test-04",
        "source_result_message_id": "msg-004",
        "task_id": "task-004",
        "correlation_id": "corr-004",
        "memory_base_commit": commit,
        "approved_by": "chief",
        "approval_status": "APPROVED",
        "approved_at": "2026-09-24T12:05:00Z"
    }

    prop_file = tmp_path / "prop.json"
    appr_file = tmp_path / "appr.json"
    prop_file.write_text(json.dumps(proposal), encoding="utf-8")
    appr_file.write_text(json.dumps(approval), encoding="utf-8")

    code = main([
        "--proposal", str(prop_file),
        "--approval", str(appr_file),
        "--memory-repo", str(mock_memory_repo),
        "--dry-run",
    ])
    assert code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "DRY_RUN_PASS"
