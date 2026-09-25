"""Seed the Cannon integration fixture tree for fresh checkouts/worktrees.

app/tests/cannon_support.py reads ROOT/data/cannon-tests/, which is
intentionally untracked. The tracked source of truth is
tmp_cannon_transfer/data/cannon-tests/. Copy it over when absent so
`pytest app/tests/test_cannon.py` works without manual setup.
Existing trees are never overwritten; content is validated by hash
on use (cannon_support.snapshot).
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tmp_cannon_transfer" / "data" / "cannon-tests"
TARGET = ROOT / "data" / "cannon-tests"

if not (TARGET / "core-source-manifest.json").is_file():
    if not (SOURCE / "core-source-manifest.json").is_file():
        raise RuntimeError(
            "Cannon fixtures missing: neither data/cannon-tests/ nor "
            "tmp_cannon_transfer/data/cannon-tests/ exists. Cannot run "
            "app/tests without the tracked fixture source.")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, TARGET)
