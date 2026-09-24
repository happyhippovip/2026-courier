import json
import pytest
from pathlib import Path

from scripts.evaluate_memory_proposal_for_auto_approval import (
    ChiefPolicyError,
    evaluate_proposal,
    process_proposal_for_chief_decision,
    main,
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
    commit = "b" * 40
    (refs_heads / "main").write_text(commit + "\n", encoding="utf-8")

    (repo / "PROJECT_STATE.md").write_text("# Project State\n", encoding="utf-8")
    (repo / "TECHNICAL_CONTEXT.md").write_text("# Technical Context\n", encoding="utf-8")
    return repo


@pytest.fixture
def base_proposal(mock_memory_repo: Path) -> dict:
    commit = "b" * 40
    return {
        "schema_version": "2.0",
        "proposal_id": "prop-mem-eval-01",
        "source_result_message_id": "msg-eval-01",
        "task_id": "task-eval-01",
        "correlation_id": "corr-eval-01",
        "memory_base_commit": commit,
        "target_files": ["TECHNICAL_CONTEXT.md"],
        "proposed_changes": [
            {
                "file": "TECHNICAL_CONTEXT.md",
                "section": "Overview",
                "action": "APPEND",
                "status_label": "VERIFIED_CURRENT",
                "proposed_text": "Verified technical fact: ffmpeg converted clip"
            }
        ],
        "reason": "Test evaluation",
        "status_labels": ["VERIFIED_CURRENT"],
        "source_references": ["result.json", "TECHNICAL_CONTEXT.md"],
        "requires_chief_approval": True,
        "created_at": "2026-09-24T12:00:00Z"
    }


def test_evaluate_proposal_auto_approve(base_proposal: dict, mock_memory_repo: Path):
    decision, reasons, labels = evaluate_proposal(base_proposal, memory_repo_path=mock_memory_repo)
    assert decision == "AUTO_APPROVE"
    assert "SAFE_VERIFIED_TECHNICAL_FACT" in reasons
    assert labels == ["VERIFIED_CURRENT"]


def test_evaluate_proposal_human_review_non_auto(base_proposal: dict, mock_memory_repo: Path):
    prop = dict(base_proposal)
    prop["proposed_changes"] = [
        {
            "file": "TECHNICAL_CONTEXT.md",
            "section": "Overview",
            "action": "APPEND",
            "status_label": "EXTERNAL_STATUS",
            "proposed_text": "External status fact"
        }
    ]
    prop["status_labels"] = ["EXTERNAL_STATUS"]

    decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=mock_memory_repo)
    assert decision == "HUMAN_REVIEW"
    assert "NON_AUTO_APPROVABLE_STATUS" in reasons


def test_evaluate_proposal_human_review_strategic(base_proposal: dict, mock_memory_repo: Path):
    prop = dict(base_proposal)
    prop["proposed_changes"] = [
        {
            "file": "TECHNICAL_CONTEXT.md",
            "section": "Overview",
            "action": "APPEND",
            "status_label": "PLANNED",
            "proposed_text": "Planned architecture evolution"
        }
    ]
    prop["status_labels"] = ["PLANNED"]

    decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=mock_memory_repo)
    assert decision == "HUMAN_REVIEW"
    assert "STRATEGIC_CHANGE" in reasons


def test_evaluate_proposal_blocked_secret(base_proposal: dict, mock_memory_repo: Path):
    prop = dict(base_proposal)
    prop["proposed_changes"] = [
        {
            "file": "TECHNICAL_CONTEXT.md",
            "section": "Overview",
            "action": "APPEND",
            "status_label": "VERIFIED_CURRENT",
            "proposed_text": "api_key = 'sk-1234567890abcdef12345678'"
        }
    ]

    decision, reasons, _ = evaluate_proposal(prop, memory_repo_path=mock_memory_repo)
    assert decision == "BLOCKED"
    assert "SECRET_DETECTED" in reasons


def test_evaluate_proposal_blocked_target_not_allowed(base_proposal: dict, mock_memory_repo: Path):
    prop = dict(base_proposal)
    prop["target_files"] = ["SECRET_PLAN.md"]
    prop["proposed_changes"] = [
        {
            "file": "SECRET_PLAN.md",
            "section": "Overview",
            "action": "APPEND",
            "status_label": "VERIFIED_CURRENT",
            "proposed_text": "Text"
        }
    ]

    decision, reasons, _ = evaluate_proposal(prop, memory_repo_path=mock_memory_repo)
    assert decision == "BLOCKED"
    assert "TARGET_NOT_ALLOWED" in reasons


def test_evaluate_proposal_blocked_head_conflict(base_proposal: dict, mock_memory_repo: Path):
    prop = dict(base_proposal)
    prop["memory_base_commit"] = "c" * 40  # Mismatched commit

    decision, reasons, _ = evaluate_proposal(prop, memory_repo_path=mock_memory_repo)
    assert decision == "BLOCKED"
    assert "MEMORY_HEAD_CONFLICT" in reasons


def test_process_proposal_auto_approve(tmp_path: Path, mock_memory_repo: Path, base_proposal: dict):
    prop_file = tmp_path / "proposal.json"
    prop_file.write_text(json.dumps(base_proposal), encoding="utf-8")

    dec_dir = tmp_path / "chief_decisions"
    appr_dir = tmp_path / "approvals"

    result = process_proposal_for_chief_decision(
        proposal_file=prop_file,
        memory_repo_path=mock_memory_repo,
        output_decisions_dir=dec_dir,
        output_approvals_dir=appr_dir,
    )

    assert result["decision"] == "AUTO_APPROVE"
    assert result["generated_approval_id"] is not None

    # Verify decision file was written
    dec_file = dec_dir / f"{base_proposal['task_id']}-chief-decision.json"
    assert dec_file.is_file()

    # Verify approval file was written
    appr_file = appr_dir / f"{base_proposal['task_id']}-auto-approval.json"
    assert appr_file.is_file()
    saved_appr = json.loads(appr_file.read_text(encoding="utf-8"))
    assert saved_appr["approval_status"] == "APPROVED"
    assert saved_appr["approved_by"] == "AUTONOMOUS_CHIEF_POLICY"


def test_main_cli(tmp_path: Path, mock_memory_repo: Path, base_proposal: dict, capsys):
    prop_file = tmp_path / "proposal.json"
    prop_file.write_text(json.dumps(base_proposal), encoding="utf-8")

    dec_dir = tmp_path / "chief_decisions_cli"
    appr_dir = tmp_path / "approvals_cli"

    code = main([
        "--proposal", str(prop_file),
        "--memory-repo", str(mock_memory_repo),
        "--output-decisions", str(dec_dir),
        "--output-approvals", str(appr_dir),
    ])
    assert code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["decision"] == "AUTO_APPROVE"
