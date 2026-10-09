"""Tests for the ``courier_core.cli`` thin wrapper (P9-cli).

``courier_core.cli:main`` is the ``courier-core`` entry point. It does no
parsing of its own: it forwards ``sys.argv`` to ``courier_core.serve.main``
and returns that call's exit code. Tests only; no behavior change.
"""

import os
import subprocess
import sys

import pytest

import courier_core.cli as cli
import courier_core.serve as serve


def test_wrapper_targets_serve_main():
    assert cli._main is serve.main


def test_main_forwards_sys_argv_and_returns_code(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "_main", lambda argv: seen.append(argv) or 0)
    argv = ["courier-core", "--home", "/tmp/nowhere"]
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 0
    assert seen == [argv]


def test_main_propagates_nonzero_exit_code(monkeypatch):
    monkeypatch.setattr(cli, "_main", lambda argv: 3)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    assert cli.main() == 3


def _clean_env():
    env = {k: v for k, v in os.environ.items()
           if k not in ("COURIER_HOME", "COURIER_LOG_LEVEL")}
    return env


def test_module_help_exits_zero_without_serving():
    proc = subprocess.run(
        [sys.executable, "-m", "courier_core.cli", "--help"],
        capture_output=True, text=True, timeout=60, env=_clean_env(),
    )
    assert proc.returncode == 0
    assert "controller" in proc.stdout.lower()


def test_bare_invocation_fails_without_serving():
    proc = subprocess.run(
        [sys.executable, "-m", "courier_core.cli"],
        capture_output=True, text=True, timeout=60, env=_clean_env(),
    )
    assert proc.returncode != 0
    assert "listening" not in proc.stderr.lower()
