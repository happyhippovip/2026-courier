#!/usr/bin/env python3
"""Tests for apply_memory_update_proposal script.

Tests section locality insertion, worktree git resolution, atomic file writes,
and memory proposal execution.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.apply_memory_update_proposal import (
    apply_memory_update_proposal,
    get_memory_commit,
    insert_into_section,
)


class TestInsertIntoSection(unittest.TestCase):
    def test_insert_between_sections(self):
        doc = (
            "# Main Doc\n\n"
            "## Section A\n"
            "Existing line in A.\n\n"
            "## Section B\n"
            "Existing line in B.\n"
        )
        result = insert_into_section(doc, "Section A", "- New Item in A")
        expected = (
            "# Main Doc\n\n"
            "## Section A\n"
            "Existing line in A.\n\n"
            "- New Item in A\n\n"
            "## Section B\n"
            "Existing line in B.\n"
        )
        self.assertEqual(result, expected)

    def test_insert_last_section(self):
        doc = (
            "# Main Doc\n\n"
            "## Section A\n"
            "Content A.\n\n"
            "## Section B\n"
            "Content B.\n"
        )
        result = insert_into_section(doc, "Section B", "- New Item in B")
        self.assertIn("Content B.\n\n- New Item in B\n", result)
        # Ensure Section A was not affected
        self.assertTrue(result.startswith("# Main Doc\n\n## Section A\nContent A.\n\n## Section B"))

    def test_insert_new_section_at_eof(self):
        doc = "# Main Doc\n\n## Section A\nContent A.\n"
        result = insert_into_section(doc, "Section C", "Content C.")
        self.assertTrue(result.endswith("## Section C\n\nContent C.\n"))

    def test_insert_with_subsections(self):
        doc = (
            "# Title\n\n"
            "## Parent Section\n"
            "Parent intro.\n\n"
            "### Subsection 1\n"
            "Sub 1 text.\n\n"
            "## Next Parent\n"
            "Next text.\n"
        )
        result = insert_into_section(doc, "Parent Section", "- Added to parent")
        # Should be placed before "## Next Parent", not before "### Subsection 1"
        self.assertTrue(result.find("- Added to parent") < result.find("## Next Parent"))
        self.assertTrue(result.find("### Subsection 1") < result.find("- Added to parent"))


class TestGetMemoryCommit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_git(self):
        self.assertEqual(get_memory_commit(self.repo_path), "0000000000000000000000000000000000000000")

    def test_direct_head_commit(self):
        git_dir = self.repo_path / ".git"
        git_dir.mkdir()
        fake_sha = "a" * 40
        (git_dir / "HEAD").write_text(fake_sha + "\n", encoding="utf-8")
        self.assertEqual(get_memory_commit(self.repo_path), fake_sha)

    def test_ref_head(self):
        git_dir = self.repo_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        heads_dir = git_dir / "refs" / "heads"
        heads_dir.mkdir(parents=True)
        fake_sha = "b" * 40
        (heads_dir / "main").write_text(fake_sha + "\n", encoding="utf-8")
        self.assertEqual(get_memory_commit(self.repo_path), fake_sha)

    def test_worktree_git_file(self):
        actual_git_dir = self.repo_path / "actual_git"
        actual_git_dir.mkdir()
        fake_sha = "c" * 40
        (actual_git_dir / "HEAD").write_text(fake_sha + "\n", encoding="utf-8")

        worktree_path = self.repo_path / "worktree"
        worktree_path.mkdir()
        (worktree_path / ".git").write_text(f"gitdir: {actual_git_dir}\n", encoding="utf-8")

        self.assertEqual(get_memory_commit(worktree_path), fake_sha)


class TestApplyMemoryUpdateProposalExecution(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.memory_repo = self.base / "memory"
        self.memory_repo.mkdir()

        # Set up git repo mock
        git_dir = self.memory_repo / ".git"
        git_dir.mkdir()
        self.fake_sha = "1" * 40
        (git_dir / "HEAD").write_text(self.fake_sha + "\n", encoding="utf-8")

        # Create canonical file
        self.project_state = self.memory_repo / "PROJECT_STATE.md"
        self.project_state.write_text(
            "# Project State\n\n"
            "## Current Focus\n"
            "- Task 1\n\n"
            "## Blockers\n"
            "- None\n",
            encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_apply_and_section_locality(self):
        proposal_data = {
            "schema_version": "2.0",
            "proposal_id": "prop-mem-001",
            "source_result_message_id": "msg-001",
            "task_id": "task-001",
            "correlation_id": "corr-001",
            "memory_base_commit": self.fake_sha,
            "target_files": ["PROJECT_STATE.md"],
            "proposed_changes": [
                {
                    "file": "PROJECT_STATE.md",
                    "section": "Current Focus",
                    "action": "APPEND",
                    "status_label": "IN PROGRESS",
                    "proposed_text": "- Task 2 in progress"
                }
            ],
            "reason": "Update focus",
            "status_labels": ["IN PROGRESS"],
            "source_references": ["ref-1"],
            "requires_chief_approval": True,
            "created_at": "2026-09-26T00:00:00Z"
        }

        approval_data = {
            "schema_version": "2.0",
            "approval_id": "appr-mem-001",
            "proposal_id": "prop-mem-001",
            "source_result_message_id": "msg-001",
            "task_id": "task-001",
            "correlation_id": "corr-001",
            "memory_base_commit": self.fake_sha,
            "approved_by": "CHIEF_01",
            "approval_status": "APPROVED",
            "approved_at": "2026-09-26T00:01:00Z"
        }

        prop_file = self.base / "proposal.json"
        appr_file = self.base / "approval.json"
        prop_file.write_text(json.dumps(proposal_data), encoding="utf-8")
        appr_file.write_text(json.dumps(approval_data), encoding="utf-8")

        result = apply_memory_update_proposal(
            proposal_file=prop_file,
            approval_file=appr_file,
            memory_repo_path=self.memory_repo,
            dry_run=False
        )

        self.assertEqual(result["status"], "APPLIED_PASS")
        self.assertEqual(result["files_modified_count"], 1)

        updated_content = self.project_state.read_text(encoding="utf-8")
        self.assertIn("- Task 2 in progress", updated_content)

        # Check section locality: Task 2 must appear before '## Blockers'
        idx_task2 = updated_content.find("- Task 2 in progress")
        idx_blockers = updated_content.find("## Blockers")
        self.assertTrue(idx_task2 < idx_blockers, "Task 2 was not inserted under Current Focus before Blockers")


if __name__ == "__main__":
    unittest.main()
