"""P9 import-surface pins for courier_worker.cli (P9-worker_cli_import).

Tests only; no behavior change. courier_worker.cli is an 8-line shim that
forwards sys.argv to courier_worker.service.main. The delegation itself
(argv passthrough, exit-code propagation, wrapper identity, error
transparency) is pinned elsewhere; these tests pin the import-time contract
instead:

- importing (or reloading) the module has no side effects: it does not
  call service.main and does not touch sys.argv;
- main() takes no parameters and reads sys.argv at call time;
- errors raised by service.main propagate unchanged;
- main is the only public callable in the module.

No network, no subprocess, no filesystem writes, no credentials.
"""

from __future__ import annotations

import inspect
import sys

import courier_worker.cli as cli
import courier_worker.service as service


def test_main_takes_no_parameters():
    assert list(inspect.signature(cli.main).parameters) == []


def test_main_is_only_public_callable():
    public_callables = {
        name
        for name, value in vars(cli).items()
        if not name.startswith("_") and callable(value)
    }
    assert public_callables == {"main"}


def test_import_does_not_call_service_main_and_keeps_argv():
    import importlib

    calls = []
    original = service.main
    argv_before = list(sys.argv)

    def fake(argv):
        calls.append(argv)
        return 0

    service.main = fake
    try:
        importlib.reload(cli)
    finally:
        service.main = original
        importlib.reload(cli)
    assert calls == []
    assert list(sys.argv) == argv_before
    assert cli._main is service.main


def test_argv_is_read_at_call_time_not_import_time(monkeypatch):
    import importlib

    seen = []
    monkeypatch.setattr(sys, "argv", ["courier-worker", "--from-import"])
    importlib.reload(cli)
    monkeypatch.setattr(cli, "_main", lambda argv: seen.append(argv) or 0)
    fresh_argv = ["courier-worker", "--from-call"]
    monkeypatch.setattr(sys, "argv", fresh_argv)
    assert cli.main() == 0
    assert seen == [fresh_argv]
    assert seen[0] is fresh_argv
    importlib.reload(cli)


def test_service_errors_propagate_unchanged(monkeypatch):
    class Boom(Exception):
        pass

    def fake(argv):
        raise Boom("noisy")

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-worker"])
    try:
        cli.main()
    except Boom as exc:
        assert str(exc) == "noisy"
    else:
        raise AssertionError("service.main error was swallowed")
