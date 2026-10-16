"""Tests for Real Antigravity Headless Execution Adapter (Mission 02)."""

import hashlib
import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from courier_adapters.antigravity_adapter import (
    AntigravityHeadlessAdapter,
    find_antigravity_cli,
    redact_secrets,
)


def test_redact_secrets():
    text = "User sk-1234567890abcdef1234567890abcdef with token: 'ghp_12345678901234567890'"
    redacted = redact_secrets(text)
    assert "sk-" not in redacted
    assert "ghp_" not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_find_antigravity_cli():
    cli = find_antigravity_cli()
    assert cli is not None
    assert Path(cli).exists()


def test_adapter_deterministic_task_success():
    """Deterministic successful execution test with mock/cli runner."""
    cli = find_antigravity_cli()
    adapter = AntigravityHeadlessAdapter(cli_path=cli)

    # Use a mock subprocess that returns 0 to verify contract and parsing
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[cli, "-p", "echo 42"],
            returncode=0,
            stdout="DETERMINISTIC_RESULT_OK\n",
            stderr="",
        )

        res = adapter.run_task(
            task_id="task-determ-01",
            dispatch_id="dsp-determ-01",
            prompt="echo 42",
            timeout_s=10.0,
        )

        assert res["task_id"] == "task-determ-01"
        assert res["dispatch_id"] == "dsp-determ-01"
        assert res["cli_started"] is True
        assert res["exit_code"] == 0
        assert res["outcome"] == "success"
        assert res["stdout"] == "DETERMINISTIC_RESULT_OK"
        assert res["timed_out"] is False
        assert len(res["sha256_stdout"]) == 64


def test_adapter_intentionally_failing_task():
    """Intentionally failing task test."""
    cli = find_antigravity_cli()
    adapter = AntigravityHeadlessAdapter(cli_path=cli)

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[cli, "-p", "invalid command"],
            returncode=2,
            stdout="",
            stderr="Error: command not recognized or permission denied\n",
        )

        res = adapter.run_task(
            task_id="task-fail-02",
            dispatch_id="dsp-fail-02",
            prompt="invalid command",
            timeout_s=5.0,
        )

        assert res["task_id"] == "task-fail-02"
        assert res["dispatch_id"] == "dsp-fail-02"
        assert res["cli_started"] is True
        assert res["exit_code"] == 2
        assert res["outcome"] == "failure"
        assert "Error: command not recognized" in res["stderr"]
        assert res["timed_out"] is False


def test_adapter_timeout_handling():
    """Timeout bounding test."""
    cli = find_antigravity_cli()
    adapter = AntigravityHeadlessAdapter(cli_path=cli)

    with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[cli], timeout=1.0)):
        res = adapter.run_task(
            task_id="task-timeout-03",
            dispatch_id="dsp-timeout-03",
            prompt="sleep 100",
            timeout_s=1.0,
        )

        assert res["timed_out"] is True
        assert res["exit_code"] == -1
        assert res["outcome"] == "failure"
