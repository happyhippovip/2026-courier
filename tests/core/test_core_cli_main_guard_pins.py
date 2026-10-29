"""P9 hardening for courier_core.cli: __main__-guard pins (tests only).

``courier_core.cli`` is an 8-line shim over ``courier_core.serve.main``.
Neighbouring open hardening work pins ``main()`` delegation, argv
passthrough and exit-code propagation with ``_main`` stubbed. This file
pins the one remaining line -- the
``if __name__ == "__main__": sys.exit(main())`` guard -- plus two offline
end-to-end spot checks proving the real entry point parses arguments
without starting any server.

No network, no filesystem writes, no real server in any test: runpy tests
stub ``courier_core.serve.main`` (the guard rebinds it at execution time),
and subprocess tests only reach argparse ``--help`` / ``parser.error``,
which both exit before ``Service`` construction (see ``serve.main``).
"""

import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import courier_core.cli as cli
import courier_core.serve as serve

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_as_main(monkeypatch, result):
    """Execute the cli module as __main__ with serve.main stubbed."""
    seen = []

    def fake(argv):
        seen.append(argv)
        return result

    monkeypatch.setattr(serve, "main", fake)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("courier_core.cli", run_name="__main__")
    return excinfo, seen


@pytest.mark.parametrize("code", [0, 3])
def test_dunder_main_guard_exits_with_main_result(monkeypatch, code):
    excinfo, seen = _run_as_main(monkeypatch, code)
    assert excinfo.value.code == code
    assert len(seen) == 1
    assert seen[0] is sys.argv


def test_import_as_module_does_not_invoke_main(monkeypatch):
    calls = []
    monkeypatch.setattr(serve, "main", lambda argv: calls.append(argv) or 0)
    namespace = runpy.run_module("courier_core.cli", run_name="courier_core.cli")
    assert calls == []
    assert namespace["__name__"] == "courier_core.cli"
    assert callable(namespace["main"])
    assert namespace["_main"] is serve.main


def test_cli_module_still_delegates_to_serve_main():
    assert cli._main is serve.main


def _scrubbed_env():
    env = dict(os.environ)
    env.pop("COURIER_HOME", None)
    return env


def test_help_exits_zero_without_starting_server():
    proc = subprocess.run(
        [sys.executable, "-m", "courier_core.cli", "--help"],
        cwd=REPO_ROOT,
        env=_scrubbed_env(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "--home" in proc.stdout


def test_missing_home_exits_two_before_binding():
    proc = subprocess.run(
        [sys.executable, "-m", "courier_core.cli"],
        cwd=REPO_ROOT,
        env=_scrubbed_env(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2
    assert "--home" in proc.stderr
