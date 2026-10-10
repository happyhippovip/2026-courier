"""P9 hardening for courier_worker.cli (guard + delegation pins).

Tests only; no behavior change. Offline, no network, no subprocess.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import courier_worker.cli as cli_mod
import courier_worker.service as service_mod


def test_import_surface_main_is_service_main():
    assert callable(cli_mod.main)
    # Delegation target is the service entry point at import time.
    assert cli_mod._main is service_mod.main


def test_main_delegates_sys_argv(monkeypatch):
    calls = {}

    def fake_main(argv):
        calls["argv"] = argv
        return 0

    monkeypatch.setattr(cli_mod, "_main", fake_main)
    sentinel = ["prog", "--controller", "http://127.0.0.1:9"]
    monkeypatch.setattr(sys, "argv", sentinel)
    assert cli_mod.main() == 0
    assert calls["argv"] is sentinel


def test_main_returns_service_codes(monkeypatch):
    for code in (0, 1, 2, 3, 4):
        monkeypatch.setattr(cli_mod, "_main", lambda argv, _c=code: _c)
        monkeypatch.setattr(sys, "argv", ["prog"])
        assert cli_mod.main() == code


def test_main_propagates_exception(monkeypatch):
    def boom(argv):
        raise RuntimeError("delegate failed")

    monkeypatch.setattr(cli_mod, "_main", boom)
    monkeypatch.setattr(sys, "argv", ["prog"])
    try:
        cli_mod.main()
    except RuntimeError as exc:
        assert str(exc) == "delegate failed"
    else:  # pragma: no cover - fail closed
        raise AssertionError("cli.main swallowed the delegate exception")


def test_main_takes_no_arguments():
    import inspect

    assert list(inspect.signature(cli_mod.main).parameters) == []


def test_main_guard_source_pins():
    src = Path(cli_mod.__file__).read_text(encoding="utf-8")
    assert 'from .service import main as _main' in src
    assert "return _main(sys.argv)" in src
    assert '__name__ == "__main__"' in src
    assert "sys.exit(main())" in src


def test_reimport_keeps_delegation():
    reloaded = importlib.reload(cli_mod)
    assert reloaded._main is service_mod.main
