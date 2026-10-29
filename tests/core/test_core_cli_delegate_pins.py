"""P9 hardening: delegate-contract pins for courier_core.cli.

``courier_core.cli.main`` is a thin shim over ``courier_core.serve.main``.
These tests pin the failure-transparency side of that contract: whatever the
serve layer raises must reach the caller unchanged (no swallow, no wrap), and
the delegation must stay a single positional call. Companion angles (argv
identity, return codes, import surface, __main__ guard) are pinned by other
P9 PRs; this file only adds the exception/call-shape edges.

All tests stub ``cli._main`` so no server ever starts: no network, no
filesystem, no subprocesses. No behavior change to the module under test.
"""

import sys

import pytest

import courier_core.cli as cli
import courier_core.serve as serve


def test_cli_wires_to_serve_main():
    assert cli._main is serve.main


def test_exception_propagates_unchanged(monkeypatch):
    boom = RuntimeError("serve exploded")

    def fake(argv):
        raise boom

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    with pytest.raises(RuntimeError) as excinfo:
        cli.main()
    assert excinfo.value is boom


def test_system_exit_propagates_unchanged(monkeypatch):
    def fake(argv):
        raise SystemExit(2)

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-core", "--bad-flag"])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 2


def test_keyboard_interrupt_propagates_unchanged(monkeypatch):
    def fake(argv):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    with pytest.raises(KeyboardInterrupt):
        cli.main()


def test_delegation_is_single_positional_arg(monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return 0

    monkeypatch.setattr(cli, "_main", fake)
    argv = ["courier-core", "--home", "/tmp/x"]
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 0
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert len(args) == 1 and args[0] is argv
    assert kwargs == {}


def test_successive_calls_delegate_independently(monkeypatch):
    seen = []

    def fake(argv):
        seen.append(argv)
        return 0

    monkeypatch.setattr(cli, "_main", fake)
    first = ["courier-core", "--port", "1"]
    second = ["courier-core", "--port", "2"]
    monkeypatch.setattr(sys, "argv", first)
    cli.main()
    monkeypatch.setattr(sys, "argv", second)
    cli.main()
    assert seen == [first, second]
    assert seen[0] is first and seen[1] is second
