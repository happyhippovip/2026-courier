"""P9 test hardening for courier_core.cli (relay pins).

Tests only; no behavior change. courier_core.cli is a small relay: main()
forwards sys.argv to courier_core.serve.main and returns its exit code.
These pins lock that relay contract with the delegate always stubbed, so
no server starts and there is no network, no credentials, and no
filesystem writes.
"""

import sys

import pytest

import courier_core.cli as CLI
import courier_core.serve as SERVE


class _Recorder:
    """Stub delegate recording how it was called."""

    def __init__(self, code=0, exc=None):
        self.code = code
        self.exc = exc
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc is not None:
            raise self.exc
        return self.code


def _stub(monkeypatch, code=0, exc=None):
    rec = _Recorder(code=code, exc=exc)
    monkeypatch.setattr(CLI, "_main", rec)
    return rec


@pytest.mark.parametrize("code", [0, 1, 2, 42])
def test_main_returns_delegate_exit_code(monkeypatch, code):
    _stub(monkeypatch, code=code)
    assert CLI.main() == code


def test_main_passes_current_argv(monkeypatch):
    rec = _stub(monkeypatch)
    sentinel = ["courier-core", "--home", "H", "--port", "0"]
    monkeypatch.setattr(sys, "argv", sentinel)
    assert CLI.main() == 0
    assert len(rec.calls) == 1
    (args, kwargs) = rec.calls[0]
    assert list(args[0]) == sentinel
    assert kwargs == {}


def test_main_forwards_argv_without_copying(monkeypatch):
    rec = _stub(monkeypatch)
    sentinel = ["courier-core"]
    monkeypatch.setattr(sys, "argv", sentinel)
    CLI.main()
    (args, _kwargs) = rec.calls[0]
    assert args[0] is sentinel


def test_main_uses_single_positional_argument(monkeypatch):
    rec = _stub(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    CLI.main()
    (args, kwargs) = rec.calls[0]
    assert len(args) == 1
    assert kwargs == {}


def test_main_propagates_delegate_exception(monkeypatch):
    boom = RuntimeError("delegate failed")
    _stub(monkeypatch, exc=boom)
    with pytest.raises(RuntimeError) as excinfo:
        CLI.main()
    assert excinfo.value is boom


def test_main_delegates_on_every_call(monkeypatch):
    rec = _stub(monkeypatch, code=0)
    assert CLI.main() == 0
    assert CLI.main() == 0
    assert len(rec.calls) == 2


def test_default_delegate_is_serve_main():
    assert CLI._main is SERVE.main
