"""Tests for courier_core.resource_sandbox - Cross-Platform Process Resource Sandbox & Isolation."""

from __future__ import annotations

import json
import sys
import pytest

from courier_core.resource_sandbox import (
    ResourceQuota,
    SandboxExecutionResult,
    ProcessSandbox,
    main,
)


def test_clean_command_execution():
    sandbox = ProcessSandbox()
    quota = ResourceQuota(
        max_memory_bytes=256 * 1024 * 1024,
        wall_timeout_seconds=5.0,
    )
    cmd = [sys.executable, "-c", "import sys; sys.stdout.write('TITAN_SANDBOX_OK'); sys.exit(0)"]
    result = sandbox.run(cmd, quota)

    assert result.is_success
    assert result.exit_code == 0
    assert result.limit_breached is None
    assert "TITAN_SANDBOX_OK" in result.stdout
    assert result.duration_seconds >= 0.0


def test_wall_timeout_breach_and_kill():
    sandbox = ProcessSandbox()
    # Very short timeout (0.5s) on command that sleeps for 5s
    quota = ResourceQuota(
        wall_timeout_seconds=0.5,
    )
    cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    result = sandbox.run(cmd, quota)

    assert not result.is_success
    assert result.limit_breached == "TIMEOUT"
    assert result.duration_seconds < 4.0


def test_non_zero_exit_code_handling():
    sandbox = ProcessSandbox()
    quota = ResourceQuota(wall_timeout_seconds=5.0)
    cmd = [sys.executable, "-c", "import sys; sys.stderr.write('ERR_TEST'); sys.exit(42)"]
    result = sandbox.run(cmd, quota)

    assert not result.is_success
    assert result.exit_code == 42
    assert result.limit_breached is None
    assert "ERR_TEST" in result.stderr


def test_quota_serialization_roundtrip():
    q = ResourceQuota(
        max_memory_bytes=512 * 1024 * 1024,
        max_cpu_seconds=10.0,
        wall_timeout_seconds=30.0,
        allow_subprocesses=False,
    )
    raw = q.to_dict()
    loaded = ResourceQuota.from_dict(raw)
    assert loaded.max_memory_bytes == q.max_memory_bytes
    assert loaded.max_cpu_seconds == q.max_cpu_seconds
    assert loaded.wall_timeout_seconds == q.wall_timeout_seconds
    assert loaded.allow_subprocesses is False


def test_result_telemetry_dictionary():
    res = SandboxExecutionResult(
        exit_code=0,
        stdout="out",
        stderr="",
        duration_seconds=1.23,
        peak_memory_bytes=10240,
        cpu_time_seconds=0.45,
        limit_breached=None,
    )
    d = res.to_dict()
    assert d["is_success"] is True
    assert d["exit_code"] == 0
    assert d["peak_memory_bytes"] == 10240


def test_cli_resource_sandbox(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "resource_sandbox.py",
            "run",
            "--cmd",
            f"{sys.executable} -c \"print('CLI_SANDBOX_OUTPUT')\"",
            "--timeout",
            "5.0",
        ],
    )
    main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["is_success"] is True
    assert "CLI_SANDBOX_OUTPUT" in data["stdout"]
