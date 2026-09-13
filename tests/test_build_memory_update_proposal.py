from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
import json
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_memory_update_proposal import ZERO_COMMIT, atomic_create_json, atomic_write_json, build_proposal_from_result, get_memory_commit, validate_proposal_against_schema


class MemoryCommitTests(unittest.TestCase):
    def test_reads_worktree_gitdir_pointer_without_git_cli(self):
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").write_text("gitdir: git-metadata\n", encoding="utf-8")
            metadata = root / "git-metadata"
            (metadata / "refs" / "heads").mkdir(parents=True)
            (metadata / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (metadata / "refs" / "heads" / "main").write_text(commit + "\n", encoding="utf-8")
            self.assertEqual(get_memory_commit(root), commit)

    def test_malformed_or_unsafe_git_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").write_text("not a gitdir pointer\n", encoding="utf-8")
            self.assertEqual(get_memory_commit(root), ZERO_COMMIT)

            metadata = root / "git-metadata"
            metadata.mkdir()
            (root / ".git").write_text("gitdir: git-metadata\n", encoding="utf-8")
            (metadata / "HEAD").write_text("ref: ../../outside\n", encoding="utf-8")
            self.assertEqual(get_memory_commit(root), ZERO_COMMIT)

    def test_same_result_replay_has_one_stable_proposal_identity(self):
        result = {
            "task_id": "task-stable",
            "message_id": "message-stable",
            "correlation_id": "correlation-stable",
            "payload": {"verified_facts": ["A local test completed."], "summary": "Test summary"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result_path = root / "result.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            first = build_proposal_from_result(result_path, memory_repo_path=root / "memory", output_dir=root / "proposals")
            second = build_proposal_from_result(result_path, memory_repo_path=root / "memory", output_dir=root / "proposals")
            self.assertEqual(first["proposal_id"], second["proposal_id"])
            self.assertEqual(first["created_at"], second["created_at"])
            saved = json.loads((root / "proposals" / "task-stable-memory-proposal.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["proposal_id"], first["proposal_id"])

    def test_different_result_cannot_overwrite_same_task_proposal(self):
        first_result = {
            "task_id": "task-collision",
            "message_id": "message-one",
            "correlation_id": "correlation-one",
            "payload": {"verified_facts": ["First immutable result."], "summary": "First"},
        }
        second_result = {
            "task_id": "task-collision",
            "message_id": "message-two",
            "correlation_id": "correlation-two",
            "payload": {"verified_facts": ["Different immutable result."], "summary": "Second"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_path, second_path = root / "first.json", root / "second.json"
            first_path.write_text(json.dumps(first_result), encoding="utf-8")
            second_path.write_text(json.dumps(second_result), encoding="utf-8")
            output_dir = root / "proposals"
            first = build_proposal_from_result(first_path, memory_repo_path=root / "memory", output_dir=output_dir)
            with self.assertRaisesRegex(SystemExit, "Proposal collision"):
                build_proposal_from_result(second_path, memory_repo_path=root / "memory", output_dir=output_dir)
            saved = json.loads((output_dir / "task-collision-memory-proposal.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["proposal_id"], first["proposal_id"])

    def test_atomic_writer_preserves_previous_artifact_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "proposal.json"
            path.write_text('{"status":"previous"}\n', encoding="utf-8")
            import build_memory_update_proposal as builder
            with mock.patch.object(builder.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    atomic_write_json(path, {"status": "new"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "previous"})
            self.assertEqual(list(path.parent.glob(".proposal.json.tmp.*")), [])

    def test_atomic_writer_syncs_directory_after_replace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "proposal.json"
            import build_memory_update_proposal as builder

            with mock.patch.object(builder.os, "fsync", wraps=builder.os.fsync) as synced:
                atomic_write_json(path, {"status": "durable"})

            self.assertGreaterEqual(synced.call_count, 2)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "durable"})

    def test_atomic_creator_has_one_winner_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "proposal.json"
            self.assertTrue(atomic_create_json(path, {"winner": 1}))
            self.assertFalse(atomic_create_json(path, {"winner": 2}))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"winner": 1})
            self.assertEqual(list(path.parent.glob(".proposal.json.tmp.*")), [])

    def test_proposal_is_scoped_to_explicit_unicode_paths_not_current_directory(self):
        result = {
            "task_id": "task-context",
            "message_id": "message-context",
            "correlation_id": "correlation-context",
            "payload": {"verified_facts": ["Explicit paths remain authoritative."], "summary": "Context test"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact_root = root / "Äußeres Verzeichnis" / "mit Leerzeichen"
            artifact_root.mkdir(parents=True)
            result_path = artifact_root / "result.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            output_dir = artifact_root / "Proposals ✓"
            unrelated_cwd = root / "unrelated-cwd"
            unrelated_cwd.mkdir()
            old_cwd = Path.cwd()
            try:
                os.chdir(unrelated_cwd)
                proposal = build_proposal_from_result(
                    result_path,
                    memory_repo_path=artifact_root / "memory",
                    output_dir=output_dir,
                )
            finally:
                os.chdir(old_cwd)

            self.assertEqual(proposal["task_id"], "task-context")
            self.assertTrue((output_dir / "task-context-memory-proposal.json").is_file())
            self.assertFalse((unrelated_cwd / "events" / "proposals").exists())

    def test_import_resolves_to_the_canonical_repository_module(self):
        import build_memory_update_proposal as builder

        self.assertEqual(Path(builder.__file__).resolve(), ROOT / "scripts" / "build_memory_update_proposal.py")

    def test_schema_boundary_rejects_invalid_correlation_and_required_types(self):
        proposal = {
            "schema_version": "2.0",
            "proposal_id": "prop-mem-task-0123456789abcdef",
            "source_result_message_id": "message",
            "task_id": "task",
            "correlation_id": "correlation",
            "memory_base_commit": "a" * 40,
            "target_files": ["TECHNICAL_CONTEXT.md"],
            "proposed_changes": [{"file": "TECHNICAL_CONTEXT.md", "action": "APPEND", "section": "State", "proposed_text": "Verified", "status_label": "VERIFIED_CURRENT"}],
            "reason": "A reason",
            "status_labels": ["VERIFIED_CURRENT"],
            "source_references": ["result.json"],
            "requires_chief_approval": True,
            "created_at": "2026-09-13T00:00:00+00:00",
        }
        valid, reason = validate_proposal_against_schema(proposal)
        self.assertTrue(valid, reason)

        proposal["correlation_id"] = {"wrong": "type"}
        valid, reason = validate_proposal_against_schema(proposal)
        self.assertFalse(valid)
        self.assertIn("correlation_id", reason)

        proposal["correlation_id"] = "correlation"
        proposal["source_references"] = [None]
        valid, reason = validate_proposal_against_schema(proposal)
        self.assertFalse(valid)
        self.assertIn("source_references", reason)


if __name__ == "__main__":
    unittest.main()
