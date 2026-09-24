"""Bounded runtime-truth collection: no single query may hang the worker."""

import subprocess
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import runtime_truth


def test_get_sha_matches_repo_head():
    repo = Path(__file__).parent.parent.resolve()
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), timeout=15
    ).decode().strip()
    assert runtime_truth.get_sha(str(repo)) == expected


def test_get_sha_without_git_or_sha_file():
    assert (
        runtime_truth.get_sha("/nonexistent-dir-xyz") == "UNKNOWN_NO_GIT_NO_SHA_FILE"
    )


def test_remote_sha_call_is_time_bounded():
    seen = {}

    def fake_check_output(*args, **kwargs):
        seen.update(kwargs)
        raise subprocess.TimeoutExpired("git", 25)

    with mock.patch.object(runtime_truth.subprocess, "check_output", fake_check_output):
        assert runtime_truth.get_remote_sha(".") == "UNKNOWN"
    assert seen.get("timeout") == 25


def test_runtime_info_completes_with_all_keys():
    info = runtime_truth.get_runtime_info()
    for key in (
        "CANONICAL_HEAD_SHA",
        "REMOTE_HEAD_SHA",
        "TESTED_SHA",
        "DEPLOYED_SHA",
        "ACTUAL_SERVING_RUNTIME_SHA",
        "ACCEPTANCE_BOUND_SHA",
        "RUNTIME_PROCESS_IDENTITY",
    ):
        assert key in info


def test_runtime_info_windows_psutil_discovery(monkeypatch, tmp_path):
    class FakeConn:
        status = "LISTEN"
        laddr = type("Addr", (), {"ip": "127.0.0.1", "port": 8080})()

    class FakeProc:
        info = {
            "pid": 9999,
            "cmdline": ["python.exe", "scripts/windows_worker/daemon.py"],
            "cwd": str(tmp_path),
        }

        def net_connections(self, kind="inet"):
            return [FakeConn()]

    class FakePsutil:
        CONN_LISTEN = "LISTEN"
        NoSuchProcess = Exception
        AccessDenied = Exception

        @staticmethod
        def process_iter(attrs):
            return [FakeProc()]

    monkeypatch.setattr(runtime_truth.sys, "platform", "win32")
    monkeypatch.setattr(runtime_truth, "psutil", FakePsutil(), raising=False)
    monkeypatch.setitem(runtime_truth.sys.modules, "psutil", FakePsutil())
    sha_file = tmp_path / ".deployed_sha"
    sha_file.write_text("fake-deployed-sha-12345", encoding="utf-8")

    info = runtime_truth.get_runtime_info()
    assert info["RUNTIME_PROCESS_IDENTITY"] == "PID:9999 EXE:python.exe"
    assert info["DEPLOYED_SHA"] == "fake-deployed-sha-12345"
    assert info["ACTUAL_SERVING_RUNTIME_SHA"] == "fake-deployed-sha-12345"
    assert info["RUNTIME_LISTENER"] == "127.0.0.1:8080"

