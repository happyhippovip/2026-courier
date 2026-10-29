"""Return-value and argv delegation pins for courier_core.cli (lane L4, P9).

Tests only: no behavior change. The shim must pass ``sys.argv`` through to
``courier_core.serve.main`` unchanged and return its exit code unchanged.
Offline, no network, no subprocesses.
"""

from __future__ import annotations

import runpy
import sys

import pytest

import courier_core.cli as CLI
from courier_core import serve as S


def test_main_passes_sys_argv_identity(monkeypatch):
    seen = {}

    def fake(argv):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(CLI, "_main", fake)
    assert CLI.main() == 0
    assert seen["argv"] is sys.argv


def test_main_returns_zero(monkeypatch):
    monkeypatch.setattr(CLI, "_main", lambda argv: 0)
    assert CLI.main() == 0


@pytest.mark.parametrize("code", [1, 2, 42])
def test_main_returns_nonzero_passthrough(monkeypatch, code):
    monkeypatch.setattr(CLI, "_main", lambda argv: code)
    result = CLI.main()
    assert result == code
    assert isinstance(result, int)


def test_main_propagates_serve_exception(monkeypatch):
    def boom(argv):
        raise RuntimeError("serve failure")

    monkeypatch.setattr(CLI, "_main", boom)
    with pytest.raises(RuntimeError):
        CLI.main()


def test_main_takes_no_arguments():
    with pytest.raises(TypeError):
        CLI.main(["unexpected"])


def test_dunder_main_guard_exits_with_serve_code(monkeypatch):
    seen = {}

    def fake(argv):
        seen["argv"] = argv
        return 3

    monkeypatch.setattr(S, "main", fake)
    saved = sys.modules.pop("courier_core.cli", None)
    try:
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("courier_core.cli", run_name="__main__")
    finally:
        sys.modules.pop("courier_core.cli", None)
        if saved is not None:
            sys.modules["courier_core.cli"] = saved
    assert exc.value.code == 3
    assert seen["argv"] is sys.argv
