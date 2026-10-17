"""P9 import-surface pins for courier_core.cli (P9-core_cli_import).

Tests only; no behavior change. courier_core.cli is an 8-line shim that
forwards sys.argv to courier_core.serve.main. The delegation itself
(argv passthrough, exit-code propagation, wrapper identity) is pinned
elsewhere; these tests pin the import-time contract instead:

- importing (or reloading) the module has no side effects: it does not
  call serve.main and does not touch sys.argv;
- main() takes no parameters and reads sys.argv at call time;
- errors raised by serve.main propagate unchanged;
- main is the only public callable in the module.

No network, no subprocess, no filesystem writes, no credentials.
"""

from __future__ import annotations

import inspect
import sys

import courier_core.cli as cli
import courier_core.serve as serve


def test_main_takes_no_parameters():
    assert list(inspect.signature(cli.main).parameters) == []


def test_main_is_only_public_callable():
    public_callables = {
        name
        for name, value in vars(cli).items()
        if not name.startswith("_") and callable(value)
    }
    assert public_callables == {"main"}


def test_import_does_not_call_serve_main_and_keeps_argv():
    import importlib

    calls = []
    original = serve.main
    argv_before = list(sys.argv)

    def fake(argv):
        calls.append(argv)
        return 0

    serve.main = fake
    try:
        importlib.reload(cli)
    finally:
        serve.main = original
        importlib.reload(cli)
    assert calls == []
    assert list(sys.argv) == argv_before
    assert cli._main is serve.main


def test_argv_is_read_at_call_time_not_import_time(monkeypatch):
    import importlib

    seen = []
    monkeypatch.setattr(sys, "argv", ["courier-core", "--from-import"])
    importlib.reload(cli)
    monkeypatch.setattr(cli, "_main", lambda argv: seen.append(argv) or 0)
    fresh_argv = ["courier-core", "--from-call"]
    monkeypatch.setattr(sys, "argv", fresh_argv)
    assert cli.main() == 0
    assert seen == [fresh_argv]
    assert seen[0] is fresh_argv
    importlib.reload(cli)


def test_serve_errors_propagate_unchanged(monkeypatch):
    class Boom(Exception):
        pass

    def fake(argv):
        raise Boom("noisy")

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    try:
        cli.main()
    except Boom as exc:
        assert str(exc) == "noisy"
    else:
        raise AssertionError("serve.main error was swallowed")
