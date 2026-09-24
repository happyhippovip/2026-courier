#!/usr/bin/env python3
"""Tests for scripts/cleanup_handler.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from scripts.cleanup_handler import release_execution_resources, main


def test_release_execution_resources_invalid_ref():
    with pytest.raises(ValueError):
        release_execution_resources("")

    with pytest.raises(ValueError):
        release_execution_resources(None)  # type: ignore


def test_release_execution_resources_locks_cleanup(tmp_path: Path):
    locks_dir = tmp_path / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)

    match_lock = locks_dir / "courier_exec_abc_run.lock"
    match_lock.write_text("locked", encoding="utf-8")

    other_lock = locks_dir / "courier_exec_other.lock"
    other_lock.write_text("locked", encoding="utf-8")

    res = release_execution_resources("exec_abc", locks_dir=locks_dir, quiet=True)
    assert res["status"] == "SUCCESS"
    assert str(match_lock) in res["released_locks"]
    assert not match_lock.exists()
    assert other_lock.exists()


def test_release_execution_resources_pid_teardown():
    mock_child = MagicMock()
    mock_child.pid = 9999
    mock_parent = MagicMock()
    mock_parent.pid = 9998
    mock_parent.children.return_value = [mock_child]

    with patch("psutil.pid_exists", return_value=True):
        with patch("psutil.Process", return_value=mock_parent):
            res = release_execution_resources("exec_pid_test", pid=9998, quiet=True)
            assert res["status"] == "SUCCESS"
            assert 9999 in res["terminated_pids"]
            assert 9998 in res["terminated_pids"]
            mock_child.terminate.assert_called_once()
            mock_parent.terminate.assert_called_once()


def test_release_execution_resources_nonexistent_pid():
    with patch("psutil.pid_exists", return_value=False):
        res = release_execution_resources("exec_pid_test", pid=8888, quiet=True)
        assert res["status"] == "SUCCESS"
        assert res["terminated_pids"] == []


def test_main_cli_with_locks(tmp_path: Path, capsys):
    locks_dir = tmp_path / "locks"
    locks_dir.mkdir()
    target_lock = locks_dir / "task_myref_run.lock"
    target_lock.write_text("test", encoding="utf-8")

    ret = main(["myref", "--locks-dir", str(locks_dir), "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["status"] == "SUCCESS"
    assert data["execution_ref"] == "myref"
    assert not target_lock.exists()
