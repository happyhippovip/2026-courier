"""P9 test hardening for courier_core.cli (shim contract pins).

Tests only; no behavior change. courier_core.cli is an 8-line shim over
courier_core.serve.main: main() forwards the live sys.argv and returns the
delegate's code. Neighbouring open hardening work already pins exit-code
relay, argv identity, RuntimeError propagation, the __main__ guard and the
import surface, so this file pins only the remaining contract edges, with
the delegate always stubbed: int return annotation, zero-parameter
signature, BaseException transparency (SystemExit / KeyboardInterrupt pass
through untouched), call-time argv re-reads (no caching), and empty-argv
passthrough. No network, no server, no filesystem writes.
"""

import inspect
import sys

import pytest

import courier_core.cli as CLI


def _stub(monkeypatch, func):
    """Replace the serve.main delegate with func; return func."""
    monkeypatch.setattr(CLI, "_main", func)
    return func


def test_main_return_annotation_is_int():
    assert inspect.signature(CLI.main).return_annotation is int


def test_main_takes_no_parameters():
    assert list(inspect.signature(CLI.main).parameters) == []


def test_system_exit_from_delegate_passes_through_unchanged(monkeypatch):
    marker = SystemExit(7)

    def delegate(argv):
        raise marker

    _stub(monkeypatch, delegate)
    with pytest.raises(SystemExit) as excinfo:
        CLI.main()
    assert excinfo.value is marker


def test_keyboard_interrupt_from_delegate_passes_through_unchanged(monkeypatch):
    marker = KeyboardInterrupt()

    def delegate(argv):
        raise marker

    _stub(monkeypatch, delegate)
    with pytest.raises(KeyboardInterrupt) as excinfo:
        CLI.main()
    assert excinfo.value is marker


def test_argv_is_reread_on_each_call(monkeypatch):
    seen = []
    _stub(monkeypatch, lambda argv: seen.append(argv) or 0)
    first = ["courier-core", "a"]
    second = ["courier-core", "b"]
    monkeypatch.setattr(sys, "argv", first)
    assert CLI.main() == 0
    monkeypatch.setattr(sys, "argv", second)
    assert CLI.main() == 0
    assert seen == [first, second]


def test_empty_argv_passes_through(monkeypatch):
    seen = []
    _stub(monkeypatch, lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", [])
    assert CLI.main() == 0
    assert seen == [[]]
