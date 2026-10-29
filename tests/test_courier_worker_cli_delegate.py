"""P9 test hardening for courier_worker.cli (sys.argv delegation pins).

``courier_worker/cli.py`` is a thin entry shim: :func:`main` forwards
``sys.argv`` unchanged to ``courier_worker.service.main`` and returns its
exit code, and the ``__main__`` guard exits via ``sys.exit(main())``.
These tests pin that contract without changing behavior. Everything here
is offline: argument parsing fails before any home, token, or network
touch, and in-process tests stub the service entry point.
"""

import os
import subprocess
import sys

import pytest

from courier_worker import cli as cli_mod
from courier_worker import service as service_mod


def test_import_exposes_main_and_stays_side_effect_free():
    assert callable(cli_mod.main)
    assert cli_mod.__name__ == "courier_worker.cli"


@pytest.mark.parametrize("code", [0, 1, 3, 4])
def test_main_forwards_sys_argv_object_and_returns_code(monkeypatch, code):
    seen = {}

    def fake_main(argv):
        seen["argv"] = argv
        return code

    sentinel = ["prog", "--controller", "http://127.0.0.1:9"]
    monkeypatch.setattr(cli_mod, "_main", fake_main)
    monkeypatch.setattr(sys, "argv", sentinel)
    assert cli_mod.main() == code
    assert seen["argv"] is sentinel


def test_main_delegates_to_service_main_by_default():
    assert cli_mod._main is service_mod.main


def test_module_entry_usage_error_is_offline_and_touch_free(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    proc = subprocess.run(
        [sys.executable, "-m", "courier_worker.cli",
         "--controller", "http://127.0.0.1:9", "--home", str(home)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    assert proc.returncode == 2
    assert b"unrecognized arguments" in proc.stderr
    assert b"courier_worker" in proc.stderr
    assert os.listdir(home) == []


def test_module_entry_help_lists_worker_options():
    proc = subprocess.run(
        [sys.executable, "-m", "courier_worker.cli", "--help"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    assert proc.returncode == 0
    assert b"--controller" in proc.stdout
    assert b"--home" in proc.stdout
    assert b"--max-tasks" in proc.stdout
