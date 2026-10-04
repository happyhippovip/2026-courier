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
