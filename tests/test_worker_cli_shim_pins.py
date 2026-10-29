"""P9 test hardening for courier_worker.cli (shim contract pins).

Tests only; no behavior change. courier_worker.cli is an 8-line shim over
courier_worker.service.main: main() forwards the live sys.argv and returns
the delegate's code. Neighbouring open hardening work already pins live-argv
identity, exit-code propagation for common codes, argv non-mutation, the
__main__ guard for one code, import side effects, and error transparency
(RuntimeError/SystemExit/KeyboardInterrupt), so this file pins only the
remaining contract edges, with the delegate always stubbed: int return
annotation, zero-parameter signature, empty-argv passthrough, positional
(not keyword) forwarding, exactly-once delegation across unusual codes,
multi-call argv re-reads including an empty middle call, and the __main__
guard for a different code with argv identity. No network, no subprocess,
no filesystem writes.
"""

from __future__ import annotations

import inspect
import runpy
import sys
import types
import warnings

import pytest

import courier_worker.cli as CLI


def _recorder(return_code):
    calls = []

    def fake(argv):
        calls.append(argv)
        return return_code

    fake.calls = calls
    return fake


def test_main_return_annotation_is_int():
    assert inspect.signature(CLI.main).return_annotation is int


def test_main_takes_no_parameters():
    assert list(inspect.signature(CLI.main).parameters) == []


def test_empty_argv_passes_through(monkeypatch):
    seen = []
    monkeypatch.setattr(CLI, "_main", lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", [])
    assert CLI.main() == 0
    assert seen == [[]]


def test_argv_forwarded_positionally_without_keywords(monkeypatch):
    received = {}

    def delegate(argv, *args, **kwargs):
        received["argv"] = argv
        received["args"] = args
        received["kwargs"] = kwargs
        return 0

    monkeypatch.setattr(CLI, "_main", delegate)
    sentinel = ["worker", "--controller", "http://127.0.0.1:9"]
    monkeypatch.setattr(sys, "argv", sentinel)
    assert CLI.main() == 0
    assert received["argv"] is sentinel
    assert received["args"] == ()
    assert received["kwargs"] == {}


def test_delegate_called_exactly_once_per_call(monkeypatch):
    for code in (0, 3, 5, 255):
        fake = _recorder(code)
        monkeypatch.setattr(CLI, "_main", fake)
        monkeypatch.setattr(sys, "argv", ["worker"])
        assert CLI.main() == code
        assert len(fake.calls) == 1


def test_unusual_exit_codes_pass_through(monkeypatch):
    for code in (5, 255):
        fake = _recorder(code)
        monkeypatch.setattr(CLI, "_main", fake)
        monkeypatch.setattr(sys, "argv", ["worker"])
        assert CLI.main() == code


def test_argv_reread_across_three_calls_with_empty_middle(monkeypatch):
    seen = []
    monkeypatch.setattr(CLI, "_main", lambda argv: seen.append(argv) or 0)
    first = ["worker", "--controller", "http://127.0.0.1:1"]
    second: list = []
    third = ["worker", "--controller", "http://127.0.0.1:3"]
    monkeypatch.setattr(sys, "argv", first)
    assert CLI.main() == 0
    monkeypatch.setattr(sys, "argv", second)
    assert CLI.main() == 0
    monkeypatch.setattr(sys, "argv", third)
    assert CLI.main() == 0
    assert seen == [first, second, third]
    assert seen[0] is first
    assert seen[1] is second
    assert seen[2] is third


def test_dunder_main_guard_exits_with_unusual_code(monkeypatch):
    sentinel = ["worker", "--controller", "http://127.0.0.1:5"]
    monkeypatch.setattr(sys, "argv", sentinel)
    stub = types.ModuleType("courier_worker.service")
    stub.main = _recorder(5)
    monkeypatch.setitem(sys.modules, "courier_worker.service", stub)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_module("courier_worker.cli", run_name="__main__")
    assert excinfo.value.code == 5
    assert stub.main.calls == [sentinel]
    assert stub.main.calls[0] is sentinel
