"""P9 test hardening for courier_worker.cli (argv passthrough pins).

Tests only; no behavior change. Pins the delegation contract of the thin
``courier_worker.cli`` wrapper: ``main()`` forwards ``sys.argv`` unchanged to
``courier_worker.service.main`` and returns its exit code, exceptions
propagate, importing the module has no side effects, and the
``__main__`` guard exits with the delegated code. No network, no
credentials, no filesystem writes.
"""

import runpy
import sys

import pytest

import courier_worker.cli as CLI


def test_main_forwards_argv_and_returns_code(monkeypatch):
    seen = {}

    def fake_main(argv):
        seen["argv"] = argv
        return 3

    monkeypatch.setattr("courier_worker.cli._main", fake_main)
    custom = ["courier-worker", "--flag", "value"]
    monkeypatch.setattr(sys, "argv", custom)
    assert CLI.main() == 3
    assert seen["argv"] is custom


@pytest.mark.parametrize("code", [0, 1, 2])
def test_main_propagates_exit_codes(monkeypatch, code):
    monkeypatch.setattr("courier_worker.cli._main", lambda argv: code)
    monkeypatch.setattr(sys, "argv", ["courier-worker"])
    assert CLI.main() == code


def test_main_passes_current_argv_object(monkeypatch):
    captured = []
    monkeypatch.setattr("courier_worker.cli._main", lambda argv: captured.append(argv) or 0)
    custom = ["courier-worker", "serve", "--port", "8080"]
    monkeypatch.setattr(sys, "argv", custom)
    CLI.main()
    assert captured == [custom]
    assert captured[0] is custom


def test_main_does_not_swallow_errors(monkeypatch):
    def boom(argv):
        raise RuntimeError("service failure")

    monkeypatch.setattr("courier_worker.cli._main", boom)
    monkeypatch.setattr(sys, "argv", ["courier-worker"])
    with pytest.raises(RuntimeError, match="service failure"):
        CLI.main()


def test_import_has_no_side_effects(monkeypatch):
    called = []
    monkeypatch.setattr("courier_worker.cli._main", lambda argv: called.append(argv) or 0)
    import importlib

    importlib.reload(CLI)
    assert called == []


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_dunder_main_guard_exits_with_delegated_code(monkeypatch):
    seen = {}

    def fake_main(argv):
        seen["argv"] = argv
        return 7

    # runpy re-executes the module source, which rebinds _main from
    # courier_worker.service; patch the source so the fresh copy uses the fake.
    monkeypatch.setattr("courier_worker.service.main", fake_main)
    custom = ["courier-worker", "--serve"]
    monkeypatch.setattr(sys, "argv", custom)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("courier_worker.cli", run_name="__main__")
    assert excinfo.value.code == 7
    assert seen["argv"] is custom
