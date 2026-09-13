from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
import json
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_memory_update_proposal import ZERO_COMMIT, atomic_write_json, build_proposal_from_result, get_memory_commit


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
            saved = json.loads((root / "proposals" / "task-stable-memory-proposal.json").read_text(encoding="utf-8"))
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


if __name__ == "__main__":
    unittest.main()
