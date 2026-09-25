"""Regression tests: memory proposal apply must be atomic and idempotent.

P0 class: a retry after an ambiguous failure must not duplicate entries,
and a crash mid-write must not truncate the memory file (tmp + replace).
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.apply_memory_update_proposal import apply_memory_update_proposal

ZERO = "0" * 40


def _write_fixtures(repo: Path):
    (repo / "DECISIONS.md").write_text("# Decisions\n", encoding="utf-8")
    proposal = {
        "schema_version": "2.0", "proposal_id": "prop-mem-t1",
        "source_result_message_id": "m1", "task_id": "t1",
        "correlation_id": "c1", "memory_base_commit": ZERO,
        "target_files": ["DECISIONS.md"],
        "proposed_changes": [{
            "file": "DECISIONS.md", "section": "Notes",
            "proposed_text": "Decision Alpha",
            "status_label": "VERIFIED_CURRENT", "action": "APPEND",
        }],
        "reason": "test", "status_labels": ["VERIFIED_CURRENT"],
        "source_references": [], "requires_chief_approval": True,
        "created_at": "2026-09-25T00:00:00Z",
    }
    approval = {
        "schema_version": "2.0", "approval_id": "appr-mem-t1",
        "proposal_id": "prop-mem-t1", "source_result_message_id": "m1",
        "task_id": "t1", "correlation_id": "c1", "memory_base_commit": ZERO,
        "approved_by": "chief", "approval_status": "APPROVED",
        "approved_at": "2026-09-25T00:00:00Z",
    }
    proposal_file = repo / "p.json"
    approval_file = repo / "a.json"
    proposal_file.write_text(json.dumps(proposal), encoding="utf-8")
    approval_file.write_text(json.dumps(approval), encoding="utf-8")
    return proposal_file, approval_file


def test_double_apply_writes_exactly_one_copy():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        proposal_file, approval_file = _write_fixtures(repo)
        first = apply_memory_update_proposal(
            proposal_file, approval_file, memory_repo_path=repo)
        assert first["status"] == "APPLIED_PASS"
        second = apply_memory_update_proposal(
            proposal_file, approval_file, memory_repo_path=repo)
        assert second["applied_changes"][0].get("skipped_duplicate") is True
        content = (repo / "DECISIONS.md").read_text(encoding="utf-8")
        assert content.count("Decision Alpha") == 1


def test_default_repo_path_honors_env_override(monkeypatch, tmp_path):
    import importlib
    import scripts.apply_memory_update_proposal as mod
    monkeypatch.setenv("COURIER_MEMORY_REPO", str(tmp_path))
    reloaded = importlib.reload(mod)
    try:
        assert reloaded.DEFAULT_MEMORY_REPO_PATH == tmp_path
    finally:
        monkeypatch.delenv("COURIER_MEMORY_REPO", raising=False)
        importlib.reload(mod)


def test_no_tmp_residue_left_behind():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        proposal_file, approval_file = _write_fixtures(repo)
        apply_memory_update_proposal(
            proposal_file, approval_file, memory_repo_path=repo)
        leftovers = list(repo.glob("*.tmp"))
        assert leftovers == []
        content = (repo / "DECISIONS.md").read_text(encoding="utf-8")
        assert "Decision Alpha" in content
