#!/usr/bin/env python3
"""Tests for scripts/studio_local_tools.py."""

from unittest.mock import MagicMock, patch
import pytest
from scripts.studio_local_tools import (
    cpu_seconds,
    classify,
    LocalToolObserver,
)


def test_cpu_seconds():
    assert cpu_seconds("01:30") == 90.0
    assert cpu_seconds("01:02:03") == 3723.0


def test_classify():
    assert classify("C:\\tools\\Antigravity.app\\run.exe") == "antigravity"
    assert classify("/Applications/ChatGPT.app/Contents/MacOS/ChatGPT") == "chatgpt"
    assert classify("codex worker") == "chatgpt"
    assert classify("/opt/bin/muse-bin-v1") == "muse"
    assert classify("notepad.exe") is None


def test_observe_windows_local():
    obs = LocalToolObserver()
    with patch("platform.system", return_value="Windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="fake_sha_123\n")
            res = obs.observe_windows(now=100.0)
            assert "windows" in res
            assert res["windows"]["status"] == "ONLINE"
            assert res["windows"]["runtime_sha"] == "fake_sha_123"


def test_snapshot_structure():
    obs = LocalToolObserver()
    snap = obs.snapshot()
    assert snap.get("source") == "LOCAL_PROCESS_OBSERVER"
    assert "tools" in snap
    for k in ("chatgpt", "muse", "antigravity"):
        assert k in snap["tools"]
        assert "status" in snap["tools"][k]
