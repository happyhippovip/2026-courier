"""Bare `muse` is not an absolute executable. This test does not launch Muse."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("fcntl")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "mac_worker"))

import muse_adapter  # noqa: E402

TASK = {"task_id": "t", "goal_id": "g", "attempt_id": "t:attempt:1",
        "dispatch_id": "d-1", "instruction": "x"}
WORKSPACE = "/Users/user/Downloads/2026-courier"


def test_missing_or_bare_muse_binary_is_not_launched():
    for capabilities in (
        {"protocol": "headless-v1"},
        {"protocol": "headless-v1", "binary": "muse"},
        {"protocol": "headless-v1", "binary": "muse.exe"},
        {"protocol": "headless-v1", "binary": "bin/muse"},
    ):
        with pytest.raises(muse_adapter.MuseCapabilityUnknown):
            muse_adapter.build_muse_command(TASK, {}, capabilities, slot_id="01", workspace=WORKSPACE)


def test_absolute_muse_binary_is_the_command():
    argv, stdin = muse_adapter.build_muse_command(
        TASK, {}, {"protocol": "headless-v1", "binary": "/opt/courier/muse"},
        slot_id="01", workspace=WORKSPACE)
    assert argv[0] == "/opt/courier/muse"
    assert argv[1] == "exec"
    assert stdin is None
