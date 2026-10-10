"""P9 test hardening for courier_worker.cli (main delegation pins).

Tests only. No behavior change. No network. No credentials.

Module under test: courier_worker/cli.py — an 8-line shim that delegates
``main()`` to ``courier_worker.service.main(sys.argv)``.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

import courier_worker.cli as cli
import courier_worker.service as service


def _argv(values):
    return list(values)


def test_main_is_same_object_as_service_main():
    assert cli._main is service.main


def test_main_takes_no_arguments():
    with pytest.raises(TypeError):
        cli.main(["unexpected"])  # type: ignore[arg-type]


def test_main_returns_int_annotation():
    assert cli.main.__annotations__.get("return") is int


def test_main_delegates_current_argv(monkeypatch):
    seen = {}

    def fake(argv):
        seen["argv"] = argv
        seen["id"] = id(argv)
        return 0

    monkeypatch.setattr(service, "main", fake)
    # Rebind the shim's reference so the test drives the real delegation line.
    monkeypatch.setattr(cli, "_main", fake)
    sentinel = _argv(["cli-prog", "--flag", "value"])
    monkeypatch.setattr(sys, "argv", sentinel)
    assert cli.main() == 0
    assert seen["argv"] == sentinel
    assert seen["id"] == id(sentinel)


@pytest.mark.parametrize("code", [0, 1, 2, 3, 42])
def test_main_propagates_return_codes(monkeypatch, code):
    monkeypatch.setattr(cli, "_main", lambda argv: code)
    monkeypatch.setattr(sys, "argv", _argv(["prog"]))
    assert cli.main() == code


def test_main_reads_argv_at_call_time(monkeypatch):
    calls = []

    def fake(argv):
        calls.append(list(argv))
        return 0

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", _argv(["prog", "first"]))
    cli.main()
    monkeypatch.setattr(sys, "argv", _argv(["prog", "second"]))
    cli.main()
    assert calls == [["prog", "first"], ["prog", "second"]]


def test_main_does_not_swallow_exceptions(monkeypatch):
    def boom(argv):
        raise RuntimeError("service failure")

    monkeypatch.setattr(cli, "_main", boom)
    monkeypatch.setattr(sys, "argv", _argv(["prog"]))
    with pytest.raises(RuntimeError, match="service failure"):
        cli.main()


def test_import_has_no_side_effects(monkeypatch):
    called = []

    import courier_worker.service as svc

    monkeypatch.setattr(svc, "main", lambda argv: called.append(argv) or 0)
    importlib.reload(cli)
    try:
        assert called == []
    finally:
        importlib.reload(cli)


def test_main_guard_calls_sys_exit_with_main():
    src = Path(cli.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and any(
                isinstance(c, ast.Constant) and c.value == "__main__"
                for c in [node.test.left, *node.test.comparators]
            )
        ):
            for stmt in ast.walk(node):
                if (
                    isinstance(stmt, ast.Call)
                    and isinstance(stmt.func, ast.Attribute)
                    and stmt.func.attr == "exit"
                    and stmt.args
                    and isinstance(stmt.args[0], ast.Call)
                    and isinstance(stmt.args[0].func, ast.Name)
                    and stmt.args[0].func.id == "main"
                ):
                    found = True
    assert found, "expected __main__ guard to call sys.exit(main())"
