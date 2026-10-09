"""Tests for the ``courier_worker.cli`` entry point wrapper (P9-worker-cli).

``courier_worker.cli:main`` is the ``courier-worker`` console script entry point.
It delegates to ``courier_worker.service.main(sys.argv)`` and propagates its exit code.
Tests only; no behavior change.
"""

import os
import subprocess
import sys
from typing import List

import pytest

import courier_worker.cli as cli
import courier_worker.service as service


def test_wrapper_targets_service_main():
    """Verify that cli._main is bound to service.main."""
    assert cli._main is service.main
    assert callable(cli.main)


def test_main_forwards_sys_argv(monkeypatch):
    """Verify that cli.main() forwards sys.argv directly to _main."""
    captured_argv: List[List[str]] = []

    def fake_main(argv):
        captured_argv.append(argv)
        return 0

    monkeypatch.setattr(cli, "_main", fake_main)
    test_argv = ["courier-worker", "--home", "/tmp/fake-home", "--controller", "http://127.0.0.1:8000"]
    monkeypatch.setattr(sys, "argv", test_argv)

    code = cli.main()
    assert code == 0
    assert len(captured_argv) == 1
    assert captured_argv[0] == test_argv


@pytest.mark.parametrize("exit_code", [0, 1, 2, 3, 4, 42])
def test_main_propagates_exit_code(monkeypatch, exit_code):
    """Verify that cli.main() propagates any integer exit code from _main."""
    monkeypatch.setattr(cli, "_main", lambda argv: exit_code)
    monkeypatch.setattr(sys, "argv", ["courier-worker"])
    assert cli.main() == exit_code


def _clean_env():
    """Scrub ambient COURIER_* environment variables for subprocess isolation."""
    return {k: v for k, v in os.environ.items()
            if not k.startswith("COURIER_")}


def test_subprocess_help_flag_exits_zero():
    """Verify that python -m courier_worker.cli --help prints usage and exits 0."""
    proc = subprocess.run(
        [sys.executable, "-m", "courier_worker.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        env=_clean_env(),
    )
    assert proc.returncode == 0
    assert "courier_worker.host" in proc.stdout
    assert "--controller" in proc.stdout


def test_subprocess_bare_invocation_exits_nonzero():
    """Verify that bare invocation fails cleanly in subprocess without serving."""
    proc = subprocess.run(
        [sys.executable, "-m", "courier_worker.cli"],
        capture_output=True,
        text=True,
        timeout=30,
        env=_clean_env(),
    )
    assert proc.returncode != 0
    combined = (proc.stdout + proc.stderr).lower()
    assert "usage" in combined or "error" in combined


def test_subprocess_invalid_flag_exits_nonzero():
    """Verify that unrecognized flags exit non-zero with an error message."""
    proc = subprocess.run(
        [sys.executable, "-m", "courier_worker.cli", "--nonexistent-option-xyz"],
        capture_output=True,
        text=True,
        timeout=30,
        env=_clean_env(),
    )
    assert proc.returncode != 0
    combined = (proc.stdout + proc.stderr).lower()
    assert "unrecognized" in combined or "error" in combined


def test_main_execution_via_script_entrypoint():
    """Verify that invoking the module as __main__ exits with the return code of main()."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, unittest.mock as m, courier_worker.cli as cli; "
            "m.patch.object(cli, '_main', return_value=7).start(); "
            "sys.exit(cli.main())",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=_clean_env(),
    )
    assert proc.returncode == 7
