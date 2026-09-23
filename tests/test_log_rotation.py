"""Tests for scripts/log_rotation.py.

Covers:
  - Old files (beyond max_age_days) are deleted
  - Recent files are kept
  - Excess files beyond max_files are deleted oldest-first
  - Non-log files are not touched
  - Empty directory does not crash
  - Non-existent directory is a no-op
  - Race condition: file deleted between glob and stat/remove does not crash
"""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
REPO = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO / "scripts"))

from log_rotation import rotate_logs


def _make_log(directory, name, age_days=0):
    """Create a .log file in directory with mtime set to `age_days` days ago."""
    path = Path(directory) / name
    path.write_text(f"log content for {name}", encoding="utf-8")
    if age_days > 0:
        old_time = time.time() - age_days * 86400
        os.utime(path, (old_time, old_time))
    return path


# ─── Age-based deletion ──────────────────────────────────────────────────────

def test_old_files_are_deleted(tmp_path):
    old = _make_log(tmp_path, "old.log", age_days=10)
    rotate_logs(str(tmp_path), max_files=100, max_age_days=7)
    assert not old.exists(), "file older than max_age_days must be deleted"


def test_recent_files_are_kept(tmp_path):
    recent = _make_log(tmp_path, "recent.log", age_days=1)
    rotate_logs(str(tmp_path), max_files=100, max_age_days=7)
    assert recent.exists(), "file within max_age_days must be kept"


def test_boundary_file_on_exact_age_is_deleted(tmp_path):
    """A file exactly at max_age_days should be deleted (mtime < threshold)."""
    boundary = _make_log(tmp_path, "boundary.log", age_days=7)
    # Slightly past the threshold
    rotate_logs(str(tmp_path), max_files=100, max_age_days=7)
    assert not boundary.exists()


# ─── Count-based deletion ─────────────────────────────────────────────────────

def test_excess_files_deleted_oldest_first(tmp_path):
    # Create 5 files with increasing age
    files = []
    for i in range(5):
        f = _make_log(tmp_path, f"log_{i:02d}.log", age_days=5 - i)  # log_00 is oldest
        files.append(f)

    rotate_logs(str(tmp_path), max_files=3, max_age_days=365)

    remaining = list(tmp_path.glob("*.log"))
    assert len(remaining) == 3

    # The 2 oldest (log_00 and log_01) must be gone
    assert not files[0].exists(), "oldest file must be deleted"
    assert not files[1].exists(), "second oldest file must be deleted"
    # The 3 newest must remain
    assert files[2].exists()
    assert files[3].exists()
    assert files[4].exists()


def test_within_max_files_no_deletion(tmp_path):
    for i in range(3):
        _make_log(tmp_path, f"log_{i}.log")
    rotate_logs(str(tmp_path), max_files=5, max_age_days=365)
    remaining = list(tmp_path.glob("*.log"))
    assert len(remaining) == 3


# ─── Non-log files untouched ─────────────────────────────────────────────────

def test_non_log_files_are_not_touched(tmp_path):
    txt = tmp_path / "notes.txt"
    txt.write_text("important notes", encoding="utf-8")
    json_f = tmp_path / "config.json"
    json_f.write_text("{}", encoding="utf-8")
    rotate_logs(str(tmp_path), max_files=0, max_age_days=0)
    assert txt.exists(), ".txt files must not be touched"
    assert json_f.exists(), ".json files must not be touched"


# ─── Edge cases ──────────────────────────────────────────────────────────────

def test_empty_directory_does_not_crash(tmp_path):
    rotate_logs(str(tmp_path), max_files=10, max_age_days=7)  # Must not raise


def test_nonexistent_directory_is_noop(tmp_path):
    missing = str(tmp_path / "does_not_exist")
    rotate_logs(missing, max_files=10, max_age_days=7)  # Must not raise


# ─── Race condition resilience ────────────────────────────────────────────────

def test_file_deleted_between_glob_and_stat_does_not_crash(tmp_path):
    """Simulate a file disappearing after glob but before stat (race condition)."""
    old = _make_log(tmp_path, "vanishing.log", age_days=10)

    original_stat = os.stat

    def flaky_stat(path, *args, **kwargs):
        if "vanishing" in str(path):
            raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
        return original_stat(path, *args, **kwargs)

    with patch("os.stat", side_effect=flaky_stat):
        rotate_logs(str(tmp_path), max_files=100, max_age_days=7)  # Must not raise


def test_file_deleted_between_stat_and_remove_does_not_crash(tmp_path):
    """Simulate a file disappearing after age check but before remove (race condition)."""
    old = _make_log(tmp_path, "vanishing2.log", age_days=10)

    original_remove = os.remove
    call_count = {"n": 0}

    def flaky_remove(path, *args, **kwargs):
        call_count["n"] += 1
        if "vanishing2" in str(path):
            raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
        return original_remove(path, *args, **kwargs)

    with patch("os.remove", side_effect=flaky_remove):
        rotate_logs(str(tmp_path), max_files=100, max_age_days=7)  # Must not raise
