import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts import log_rotation


def test_rotate_logs_basic(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create 5 log files with different modification times
    for i in range(5):
        f = log_dir / f"test_{i}.log"
        f.write_text(f"log data {i}")
        # Set mtime backwards
        mtime = time.time() - (5 - i) * 100
        os.utime(f, (mtime, mtime))

    # Keep only 3
    log_rotation.rotate_logs(log_dir=str(log_dir), max_files=3, max_age_days=10)

    remaining = list(log_dir.glob("*.log"))
    assert len(remaining) == 3
    remaining_names = {p.name for p in remaining}
    assert "test_0.log" not in remaining_names
    assert "test_1.log" not in remaining_names
    assert "test_4.log" in remaining_names


def test_rotate_logs_age_threshold(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    old_file = log_dir / "old.log"
    old_file.write_text("old data")
    old_mtime = time.time() - (10 * 86400)
    os.utime(old_file, (old_mtime, old_mtime))

    fresh_file = log_dir / "fresh.log"
    fresh_file.write_text("fresh data")

    log_rotation.rotate_logs(log_dir=str(log_dir), max_files=10, max_age_days=7)

    assert not old_file.exists()
    assert fresh_file.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows specific locked file test")
def test_rotate_logs_resilient_to_windows_locked_files(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create 4 old files
    files = []
    for i in range(4):
        f = log_dir / f"daemon_{i}.log"
        f.write_text(f"daemon log {i}")
        old_mtime = time.time() - (15 * 86400)
        os.utime(f, (old_mtime, old_mtime))
        files.append(f)

    # Keep daemon_0.log open with write lock (simulating running daemon on Windows)
    import msvcrt
    with open(files[0], "r+b") as locked_handle:
        msvcrt.locking(locked_handle.fileno(), msvcrt.LK_NBLCK, 1)

        # rotate_logs should NOT crash with PermissionError / WinError 32
        # It should skip the locked file gracefully and continue removing other old files!
        log_rotation.rotate_logs(log_dir=str(log_dir), max_files=1, max_age_days=7)

    # The locked file should still exist, but unlocked old files should be removed
    assert files[0].exists()
    assert not files[1].exists()
    assert not files[2].exists()
    assert not files[3].exists()


def test_rotate_logs_nonexistent_dir(tmp_path):
    result = log_rotation.rotate_logs(log_dir=str(tmp_path / "nonexistent"))
    assert result == {"removed": 0, "skipped_locked": 0}


def test_rotate_logs_max_bytes(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    large_file = log_dir / "large.log"
    large_file.write_text("x" * 2000)

    small_file = log_dir / "small.log"
    small_file.write_text("x" * 50)

    log_rotation.rotate_logs(log_dir=str(log_dir), max_files=10, max_age_days=30, max_bytes=1000)

    assert not large_file.exists()
    assert (log_dir / "large.log.1").exists()
    assert small_file.exists()

