"""P9 test hardening for courier_worker.cli (delegation pins, tests-only).

courier_worker/cli.py is an 8-line shim: main() forwards sys.argv to
courier_worker.service.main and returns its exit code. These pins lock that
wire discipline without behavior change and without network use.
"""

from __future__ import annotations

import sys

import courier_worker.cli as cli_mod
from courier_worker import service as service_mod


def test_main_delegates_sys_argv(monkeypatch):
    seen = {}

    def fake_main(argv):
        seen["argv"] = argv
        seen["is_sys_argv"] = argv is sys.argv
        return 0

    monkeypatch.setattr(cli_mod, "_main", fake_main)
    monkeypatch.setattr(sys, "argv", ["prog", "--controller", "http://x"])
    assert cli_mod.main() == 0
    assert seen["argv"] == ["prog", "--controller", "http://x"]
    assert seen["is_sys_argv"] is True


def test_main_propagates_exit_codes(monkeypatch):
    for code in (0, 2, 3, 4):
        monkeypatch.setattr(cli_mod, "_main", lambda argv, _c=code: _c)
        assert cli_mod.main() == code


def test_main_uses_service_main_reference(monkeypatch):
    # The shim binds service.main at import as _main; main() must call it.
    calls = []

    def fake_main(argv):
        calls.append(list(argv))
        return 7

    monkeypatch.setattr(cli_mod, "_main", fake_main)
    monkeypatch.setattr(sys, "argv", ["courier-worker", "--controller", "http://y"])
    assert cli_mod.main() == 7
    assert calls == [["courier-worker", "--controller", "http://y"]]


def test_main_does_not_swallow_system_exit(monkeypatch):
    import pytest

    def fake_main(argv):
        raise SystemExit(2)

    monkeypatch.setattr(cli_mod, "_main", fake_main)
    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    assert exc.value.code == 2


def test_shim_binds_service_main():
    assert cli_mod._main is service_mod.main


def test_cli_module_has_main_guard():
    import pathlib

    src = pathlib.Path(cli_mod.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in src
    assert "sys.exit(main())" in src
