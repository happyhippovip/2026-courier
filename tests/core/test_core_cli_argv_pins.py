"""P9 hardening pins for courier_core.cli (tests-only, no behavior change).

``courier_core.cli.main`` is a thin shim over ``courier_core.serve.main``: it
passes the current ``sys.argv`` through and returns the exit code. These tests
pin argv passthrough and exit-code propagation with ``serve.main`` always
stubbed, so no server ever starts (no network, no processes, no filesystem).
"""

import inspect
import sys

import pytest

import courier_core.cli as cli
import courier_core.serve as serve


def _stub_returning(code):
    calls = []

    def fake(argv):
        calls.append(argv)
        return code

    fake.calls = calls
    return fake


def test_main_passes_current_sys_argv(monkeypatch):
    stub = _stub_returning(0)
    monkeypatch.setattr(cli, "_main", stub)
    monkeypatch.setattr(sys, "argv", ["cli", "--home", "/tmp/x", "--port", "0"])
    assert cli.main() == 0
    assert stub.calls == [["cli", "--home", "/tmp/x", "--port", "0"]]


@pytest.mark.parametrize("code", [0, 1, 2, 42])
def test_main_propagates_return_code(monkeypatch, code):
    stub = _stub_returning(code)
    monkeypatch.setattr(cli, "_main", stub)
    monkeypatch.setattr(sys, "argv", ["cli"])
    assert cli.main() == code


def test_main_reads_argv_at_call_time_not_import_time(monkeypatch):
    stub = _stub_returning(0)
    monkeypatch.setattr(cli, "_main", stub)
    monkeypatch.setattr(sys, "argv", ["cli", "--port", "1"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["cli", "--port", "2"])
    cli.main()
    assert stub.calls == [["cli", "--port", "1"], ["cli", "--port", "2"]]


def test_main_takes_no_arguments():
    assert inspect.signature(cli.main).parameters == {}
    with pytest.raises(TypeError):
        cli.main(["unexpected"])


def test_cli_delegates_to_serve_main():
    assert cli._main is serve.main


def test_main_does_not_swallow_system_exit(monkeypatch):
    def fake(argv):
        raise SystemExit(2)

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["cli", "--bad-flag"])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 2
