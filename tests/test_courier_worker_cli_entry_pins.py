"""Entry pins for courier_worker.cli (lane L4, P9 tests-only).

The worker CLI is an 8-line shim: ``main()`` hands ``sys.argv`` to
``courier_worker.service.main`` and returns its exit code, and the
``__main__`` guard wires ``sys.exit(main())``. Nothing here changes
behavior; the tests pin the wiring so a future refactor cannot silently
break the entry point:

- the exact ``sys.argv`` object reaches the service entry point;
- integer return codes (0 and non-zero) propagate verbatim;
- ``SystemExit`` / errors from argument parsing propagate (never swallowed);
- ``python -m courier_worker.cli --help`` exits 0 without any network.

No network calls, no credentials, stdlib only.
"""

from __future__ import annotations

import socket
import subprocess
import sys

import pytest

import courier_worker.cli as cli
from courier_worker import service as service_mod


def test_main_passes_argv_object_through(monkeypatch):
    seen = {}

    def stub(argv):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(cli, "_main", stub)
    sentinel = ["worker-prog", "--controller", "http://127.0.0.1:9"]
    monkeypatch.setattr(sys, "argv", sentinel)
    assert cli.main() == 0
    assert seen["argv"] is sentinel


def test_main_returns_zero_verbatim(monkeypatch):
    monkeypatch.setattr(cli, "_main", lambda argv: 0)
    assert cli.main() == 0


def test_main_returns_nonzero_verbatim(monkeypatch):
    monkeypatch.setattr(cli, "_main", lambda argv: 3)
    assert cli.main() == 3


def test_main_does_not_swallow_system_exit(monkeypatch):
    def stub(argv):
        raise SystemExit(2)

    monkeypatch.setattr(cli, "_main", stub)
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 2


def test_main_does_not_swallow_runtime_error(monkeypatch):
    def stub(argv):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "_main", stub)
    with pytest.raises(RuntimeError, match="boom"):
        cli.main()


def test_main_delegates_to_service_main():
    assert cli._main is service_mod.main


def test_real_passthrough_reports_argv_zero_without_network(monkeypatch, tmp_path):
    # End to end through the real service entry point: argv[0] is passed
    # through as-is, so argument parsing stops with exit 2 before any
    # socket is created. The controller address is unreachable on purpose;
    # parsing must fail first (no network attempted).
    def _no_socket(*args, **kwargs):
        raise AssertionError("must not create a socket during argument parsing")

    monkeypatch.setattr(socket, "socket", _no_socket)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--home", str(tmp_path), "--controller", "http://127.0.0.1:9"],
    )
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 2


def test_module_as_main_help_exits_zero_offline():
    proc = subprocess.run(
        [sys.executable, "-m", "courier_worker.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert "usage:" in proc.stdout
