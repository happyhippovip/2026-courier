"""P9 hardening for courier_core.cli: exit-propagation pins (tests only).

``courier_core.cli.main`` is a thin shim over ``courier_core.serve.main``:
it passes the current ``sys.argv`` through and returns the exit code
unchanged. Earlier open hardening PRs pin delegation and basic argv
passthrough; these tests pin the exit path itself: integer codes pass
through without masking, and exceptional exits (``SystemExit`` variants,
``KeyboardInterrupt``, other errors) propagate unchanged.

All tests stub ``cli._main`` so no server starts: no network, no
filesystem, no subprocesses.
"""

import sys

import pytest

import courier_core.cli as cli
import courier_core.serve as serve


def test_wires_to_serve_main():
    assert cli._main is serve.main


@pytest.mark.parametrize("code", [0, 1, 2, 99, 255, 256, -1])
def test_exit_code_passes_through_unmasked(monkeypatch, code):
    monkeypatch.setattr(cli, "_main", lambda argv: code)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    assert cli.main() == code


def test_exit_path_receives_current_argv(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "_main", lambda argv: seen.append(argv) or 7)
    argv = ["courier-core", "--home", "home-a", "--port", "0"]
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 7
    assert seen == [argv]
    assert seen[0] is argv


@pytest.mark.parametrize("code", [0, 2, "boom", None, (1, 2)])
def test_system_exit_propagates_with_same_code(monkeypatch, code):
    def fake(argv):
        raise SystemExit(code)

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == code


def test_keyboard_interrupt_propagates(monkeypatch):
    def fake(argv):
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    with pytest.raises(KeyboardInterrupt):
        cli.main()


def test_runtime_error_propagates_unchanged(monkeypatch):
    marker = RuntimeError("exit-path must stay transparent")

    def fake(argv):
        raise marker

    monkeypatch.setattr(cli, "_main", fake)
    monkeypatch.setattr(sys, "argv", ["courier-core"])
    with pytest.raises(RuntimeError) as excinfo:
        cli.main()
    assert excinfo.value is marker


def test_main_takes_no_arguments():
    with pytest.raises(TypeError):
        cli.main(["unexpected"])


def test_main_annotation_returns_int():
    assert cli.main.__annotations__.get("return") is int
