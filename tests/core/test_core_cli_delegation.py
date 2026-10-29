"""P9 hardening: courier_core.cli delegates to courier_core.serve.main.

The installed console entry point (``courier-core = courier_core.cli:main``)
must hand the process argv to the serve layer verbatim and propagate its
integer exit code. These tests replace ``serve.main`` with a fake, so they
touch no network, no filesystem and no subprocesses.
"""

import sys

import courier_core.cli as core_cli
import courier_core.serve as serve


def test_cli_wires_to_serve_main():
    assert core_cli._main is serve.main


def test_main_passes_argv_verbatim(monkeypatch):
    seen = []

    def fake(argv):
        seen.append(argv)
        return 0

    monkeypatch.setattr(core_cli, "_main", fake)
    argv = ["courier-core", "--home", "/tmp/x", "--port", "0"]
    monkeypatch.setattr(sys, "argv", argv)
    assert core_cli.main() == 0
    assert seen == [argv]
    assert seen[0] is argv


def test_main_propagates_nonzero_exit(monkeypatch):
    monkeypatch.setattr(core_cli, "_main", lambda argv: 3)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    assert core_cli.main() == 3


def test_main_calls_serve_exactly_once(monkeypatch):
    calls = []

    def fake(argv):
        calls.append(list(argv))
        return 0

    monkeypatch.setattr(core_cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-core", "--print-port"])
    core_cli.main()
    assert len(calls) == 1


def test_main_uses_current_argv_at_call_time(monkeypatch):
    received = []
    monkeypatch.setattr(core_cli, "_main", lambda argv: received.append(argv) or 0)
    first = ["courier-core", "--home", "a"]
    second = ["courier-core", "--home", "b"]
    monkeypatch.setattr(sys, "argv", first)
    core_cli.main()
    monkeypatch.setattr(sys, "argv", second)
    core_cli.main()
    assert received == [first, second]


def test_main_does_not_mutate_argv(monkeypatch):
    monkeypatch.setattr(core_cli, "_main", lambda argv: 0)
    argv = ["courier-core", "--home", "/tmp/x"]
    snapshot = list(argv)
    monkeypatch.setattr(sys, "argv", argv)
    core_cli.main()
    assert argv == snapshot
