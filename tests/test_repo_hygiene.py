"""Generated runtime state must not be tracked (public-repo exposure, 2026-10-01 48f7b8bb)."""
import os
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORBIDDEN_PREFIXES = (
    "runtime/muse-data/",
    "runtime/slots/",
    "runtime/win_slots/",
    "scripts/revenue_worker_state/",
    ".tmp_pytest/",
)


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")


def test_no_generated_runtime_state_is_tracked():
    tracked = [p for p in _git("ls-files").splitlines() if p.startswith(FORBIDDEN_PREFIXES)]
    assert tracked == [], f"generated runtime state is tracked: {tracked[:5]} (+{max(0, len(tracked) - 5)})"


def test_no_gitlinks_without_gitmodules():
    gitlinks = [line.split("\t", 1)[1] for line in _git("ls-files", "-s").splitlines() if line.startswith("160000 ")]
    if gitlinks:
        assert os.path.exists(os.path.join(REPO, ".gitmodules")), f"embedded repos without .gitmodules: {gitlinks}"

def test_no_tracked_crash_logs():
    tracked = [p for p in _git("ls-files").splitlines() if p.endswith(".log") or p.endswith(".out")]
    assert tracked == [], f"crash logs or output logs are tracked: {tracked[:5]} (+{max(0, len(tracked) - 5)})"

def test_no_tracked_root_temp_files():
    temp_prefixes = (
        "mytmp/", "mytemp/", "mytempdir/", "mytmp2/", "temp/", "temp_dir/", "temp_dir2/",
        "test_tmp_path", "results"
    )
    temp_suffixes = (
        ".xml", ".coverage", "pytest.log"
    )
    tracked = [p for p in _git("ls-files").splitlines() if (p.startswith(temp_prefixes) or p.endswith(temp_suffixes) or p == ".coverage" or p == "temp_test.py" or p.startswith("temp_queue")) and not p.startswith("test_")]
    # filter out tests/ and other valid stuff, only root temp files
    tracked = [p for p in tracked if not (p.startswith("tests/") or p.startswith("scripts/"))]
    assert tracked == [], f"temp files or outputs are tracked: {tracked[:5]} (+{max(0, len(tracked) - 5)})"

