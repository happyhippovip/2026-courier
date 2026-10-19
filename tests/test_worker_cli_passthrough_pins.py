"""P9 hardening pins for courier_worker.cli (tests only, no behavior change).

courier_worker.cli is a thin delegation shim: main() must forward the live
sys.argv to courier_worker.service.main and return its exit code, and the
__main__ guard must exit with that code. These pins lock that contract
offline (no network, no subprocess worker, no credentials).
"""

import runpy
import sys
import types
import warnings

import pytest

import courier_worker.cli as cli


def _recorder(return_code):
    calls = []

    def fake(argv):
        calls.append(argv)
        return return_code

    fake.calls = calls
    return fake


def test_delegation_target_is_service_main():
    import courier_worker.service as service

    assert cli._main is service.main


def test_main_passes_live_argv_object(monkeypatch):
    fake = _recorder(0)
    monkeypatch.setattr(cli, "_main", fake)
    sentinel = ["worker", "--home", "some-home"]
    monkeypatch.setattr(sys, "argv", sentinel)
    assert cli.main() == 0
    assert len(fake.calls) == 1
    assert fake.calls[0] is sentinel


def test_main_propagates_exit_code(monkeypatch):
    for code in (0, 1, 2, 7):
        fake = _recorder(code)
        monkeypatch.setattr(cli, "_main", fake)
        monkeypatch.setattr(sys, "argv", ["worker"])
        assert cli.main() == code


def test_main_does_not_mutate_argv(monkeypatch):
    fake = _recorder(0)
    monkeypatch.setattr(cli, "_main", fake)
    argv = ["worker", "--flag", "value"]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    assert argv == ["worker", "--flag", "value"]


def test_main_entrypoint_signature():
    assert callable(cli.main)


def test_dunder_main_guard_exits_with_service_code(monkeypatch):
    sentinel = ["worker", "--home", "some-home"]
    monkeypatch.setattr(sys, "argv", sentinel)
    stub = types.ModuleType("courier_worker.service")
    stub.main = _recorder(3)
    monkeypatch.setitem(sys.modules, "courier_worker.service", stub)
    with warnings.catch_warnings():
        # runpy re-executes an already-imported module; that warning is benign.
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_module("courier_worker.cli", run_name="__main__")
    assert excinfo.value.code == 3
    assert stub.main.calls == [sentinel]
    assert stub.main.calls[0] is sentinel


def test_import_has_no_side_effects():
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-c", "import courier_worker.cli"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert proc.stdout == ""
