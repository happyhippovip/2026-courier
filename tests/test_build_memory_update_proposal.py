from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_memory_update_proposal import ZERO_COMMIT, get_memory_commit


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


if __name__ == "__main__":
    unittest.main()
