"""Tests-only hardening for courier_worker.cli (P9-worker_cli).

The module is a thin delegation shim over courier_worker.service.main.
These tests pin the delegation contract without any network access:
the service entry point is always replaced with a stub.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import sys

import pytest

import courier_worker.cli as cli


def test_main_passes_sys_argv_through_exactly():
    sentinel = ["courier_worker.cli", "--controller", "http://127.0.0.1:9"]
    with patch.object(sys, "argv", sentinel), patch.object(
        cli, "_main", return_value=0
    ) as stub:
        assert cli.main() == 0
    stub.assert_called_once_with(sentinel)
    assert stub.call_args[0][0] is sentinel


@pytest.mark.parametrize("code", [0, 1, 2, 3, 4, 7])
def test_main_propagates_return_code(code):
    with patch.object(cli, "_main", return_value=code) as stub:
        assert cli.main() == code
    stub.assert_called_once()


def test_main_takes_no_arguments():
    with pytest.raises(TypeError):
        cli.main(["unexpected"])


def test_main_does_not_swallow_exceptions():
    with patch.object(cli, "_main", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            cli.main()


def test_main_propagates_system_exit():
    with patch.object(cli, "_main", side_effect=SystemExit(2)):
        with pytest.raises(SystemExit) as excinfo:
            cli.main()
    assert excinfo.value.code == 2


def test_import_has_no_side_effects():
    with patch("courier_worker.service.main") as service_main:
        exec(
            compile(
                "from courier_worker.service import main as _main",
                "courier_worker/cli.py",
                "exec",
            ),
            {"__name__": "courier_worker.cli", "__package__": "courier_worker"},
        )
    service_main.assert_not_called()


def test_dunder_main_guard_delegates_and_exits():
    source = (
        Path(__file__).resolve().parent.parent / "courier_worker" / "cli.py"
    ).read_text()
    sentinel = ["courier_worker.cli", "--controller", "http://127.0.0.1:9"]
    namespace = {"__name__": "__main__", "__package__": "courier_worker"}
    with patch.object(sys, "argv", sentinel), patch(
        "courier_worker.service.main", return_value=5
    ) as service_main, patch.object(sys, "exit") as do_exit:
        exec(compile(source, "courier_worker/cli.py", "exec"), namespace)
        assert namespace["main"]() == 5
    assert service_main.call_count == 2
    service_main.assert_called_with(sentinel)
    do_exit.assert_called_once_with(5)
