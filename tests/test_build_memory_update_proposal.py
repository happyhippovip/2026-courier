import json
import pytest
from pathlib import Path

from scripts.build_memory_update_proposal import (
    MemoryProposalError,
    build_proposal_from_result,
    get_memory_commit,
    main,
    validate_proposal_against_schema,
)


@pytest.fixture
def mock_memory_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "memory_repo"
    repo.mkdir()
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    refs_heads = git_dir / "refs" / "heads"
    refs_heads.mkdir(parents=True)
    commit = "a" * 40
    (refs_heads / "main").write_text(commit + "\n", encoding="utf-8")

    (repo / "PROJECT_STATE.md").write_text("# Project State\n\n## Overview\nInitial content\n", encoding="utf-8")
    (repo / "TECHNICAL_CONTEXT.md").write_text("# Technical Context\n\n## Overview\nInitial technical content\n", encoding="utf-8")
    return repo


@pytest.fixture
def sample_result_file(tmp_path: Path) -> Path:
    res = {
        "message_id": "msg-agy-100",
        "task_id": "task-test-100",
        "correlation_id": "corr-test-100",
        "payload": {
            "summary": "Completed video export and TikTok token check",
            "verified_facts": [
                "Local rendering engine completed video in 3.4 seconds",
                "TIKTOK auth status checked: missing token",
                "CONFLICT found between cache and local state",
                "UNKNOWN response code from upstream gateway",
                "PAUSED due to human gate approval requirement"
            ]
        }
    }
    p = tmp_path / "result-100.json"
    p.write_text(json.dumps(res), encoding="utf-8")
    return p


def test_get_memory_commit(mock_memory_repo: Path):
    commit = get_memory_commit(mock_memory_repo)
    assert commit == "a" * 40

    non_repo = mock_memory_repo.parent / "non_repo"
    non_repo.mkdir()
    assert get_memory_commit(non_repo) == "0000000000000000000000000000000000000000"


def test_validate_proposal_against_schema(mock_memory_repo: Path):
    commit = get_memory_commit(mock_memory_repo)
    valid_prop = {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-task-01",
        "source_result_message_id": "msg-001",
        "task_id": "task-01",
        "correlation_id": "corr-01",
        "memory_base_commit": commit,
        "target_files": ["TECHNICAL_CONTEXT.md"],
        "proposed_changes": [
            {
                "file": "TECHNICAL_CONTEXT.md",
                "section": "Current verified local technical state",
                "action": "APPEND",
                "status_label": "VERIFIED_CURRENT",
                "proposed_text": "Fact 1"
            }
        ],
        "reason": "Test proposal",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["result.json", "TECHNICAL_CONTEXT.md"],
        "requires_chief_approval": True,
        "created_at": "2026-09-24T12:00:00Z"
    }

    ok, msg = validate_proposal_against_schema(valid_prop)
    assert ok is True
    assert msg == "VALID"

    # Invalid: missing field
    invalid_prop = dict(valid_prop)
    del invalid_prop["reason"]
    ok, msg = validate_proposal_against_schema(invalid_prop)
    assert ok is False
    assert "Field mismatch" in msg

    # Invalid: wrong schema_version
    invalid_ver = dict(valid_prop, schema_version="1.0")
    ok, msg = validate_proposal_against_schema(invalid_ver)
    assert ok is False
    assert "Invalid schema_version" in msg

    # Invalid: requires_chief_approval must be True
    invalid_gate = dict(valid_prop, requires_chief_approval=False)
    ok, msg = validate_proposal_against_schema(invalid_gate)
    assert ok is False
    assert "requires_chief_approval must be strictly boolean True" in msg


def test_build_proposal_from_result(tmp_path: Path, mock_memory_repo: Path, sample_result_file: Path):
    out_dir = tmp_path / "proposals"
    proposal = build_proposal_from_result(
        result_file=sample_result_file,
        memory_repo_path=mock_memory_repo,
        output_dir=out_dir,
    )

    assert proposal["task_id"] == "task-test-100"
    assert proposal["source_result_message_id"] == "msg-agy-100"
    assert proposal["memory_base_commit"] == "a" * 40
    assert proposal["requires_chief_approval"] is True
    assert len(proposal["proposed_changes"]) == 5

    # Check labels derived from verified facts
    labels = proposal["status_labels"]
    assert "VERIFIED_CURRENT" in labels
    assert "EXTERNAL_STATUS" in labels
    assert "CONFLICT" in labels
    assert "UNKNOWN" in labels
    assert "PAUSED_EXTERNAL_GATE" in labels

    # Check written file exists and matches
    out_file = out_dir / "task-test-100-memory-proposal.json"
    assert out_file.is_file()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["proposal_id"] == proposal["proposal_id"]


def test_build_proposal_fallback_summary(tmp_path: Path, mock_memory_repo: Path):
    res = {
        "message_id": "msg-002",
        "task_id": "task-002",
        "correlation_id": "corr-002",
        "payload": {
            "summary": "Fallback summary only",
            "verified_facts": []
        }
    }
    p = tmp_path / "result-no-facts.json"
    p.write_text(json.dumps(res), encoding="utf-8")

    out_dir = tmp_path / "proposals_fallback"
    proposal = build_proposal_from_result(
        result_file=p,
        memory_repo_path=mock_memory_repo,
        output_dir=out_dir,
    )
    assert len(proposal["proposed_changes"]) == 1
    assert "Fallback summary only" in proposal["proposed_changes"][0]["proposed_text"]


def test_build_proposal_missing_result_error(tmp_path: Path, mock_memory_repo: Path):
    with pytest.raises(MemoryProposalError, match="Result file not found"):
        build_proposal_from_result(
            result_file=tmp_path / "non_existent.json",
            memory_repo_path=mock_memory_repo,
        )


def test_main_cli(tmp_path: Path, mock_memory_repo: Path, sample_result_file: Path, capsys):
    out_dir = tmp_path / "cli_proposals"
    code = main([
        "--result", str(sample_result_file),
        "--memory-repo", str(mock_memory_repo),
        "--output-dir", str(out_dir),
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["task_id"] == "task-test-100"

    prop_file = out_dir / "task-test-100-memory-proposal.json"
    assert prop_file.is_file()

    # CLI validate existing proposal
    val_code = main([
        "--validate-proposal", str(prop_file),
        "--json",
    ])
    assert val_code == 0
    captured = capsys.readouterr()
    val_data = json.loads(captured.out)
    assert val_data["status"] == "VALID"

    # CLI missing --result
    err_code = main([])
    assert err_code == 1
