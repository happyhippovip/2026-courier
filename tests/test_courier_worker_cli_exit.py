"""Tests-only hardening for courier_worker.cli exit propagation (P9-worker_cli_exit).

The module is a two-line delegation shim over courier_worker.service.main.
Sibling pins cover the delegation shape itself (P9-worker_cli: argv identity
for one call, return codes 0/1/2/3/4/7, TypeError, RuntimeError and
SystemExit transparency, exec-based __main__ guard; P9-worker-cli: entry
point binding plus subprocess --help / bare invocation). This file pins the
complementary exit-propagation contract:

- the call shape is exactly one positional argument with no keywords;
- sys.argv is read fresh on every call (no stale capture across calls);
- BaseException transparency (KeyboardInterrupt is never swallowed);
- the real ``__main__`` path via runpy exits with the stubbed service code.

Tests only; no behavior change. No network: service.main is always stubbed
in-process and no subprocess is spawned.
"""

from __future__ import annotations

import runpy
import sys
from unittest.mock import patch

import pytest

import courier_worker.cli as cli


def test_main_calls_with_single_positional_and_no_kwargs():
    sentinel = ["courier-worker", "--controller", "http://127.0.0.1:9"]
    with patch.object(sys, "argv", sentinel), patch.object(
        cli, "_main", return_value=0
    ) as stub:
        assert cli.main() == 0
    stub.assert_called_once()
    args, kwargs = stub.call_args
    assert len(args) == 1
    assert args[0] is sentinel
    assert kwargs == {}


def test_main_reads_argv_fresh_on_each_call():
    first = ["courier-worker", "--controller", "http://127.0.0.1:9"]
    second = ["courier-worker", "--controller", "http://127.0.0.1:10"]
    seen = []
    with patch.object(cli, "_main", side_effect=lambda argv: seen.append(argv) or 0):
        with patch.object(sys, "argv", first):
            assert cli.main() == 0
        with patch.object(sys, "argv", second):
            assert cli.main() == 0
    assert seen == [first, second]
    assert seen[0] is first
    assert seen[1] is second


@pytest.mark.parametrize("code", [5, 9, 13, 99, 255])
def test_main_propagates_distinct_exit_codes(code):
    with patch.object(cli, "_main", return_value=code) as stub:
        result = cli.main()
    assert result == code
    assert isinstance(result, int)
    stub.assert_called_once()


def test_main_does_not_swallow_keyboard_interrupt():
    with patch.object(cli, "_main", side_effect=KeyboardInterrupt()):
        with pytest.raises(KeyboardInterrupt):
            cli.main()


def test_dunder_main_via_runpy_exits_with_service_code():
    sentinel = ["courier-worker", "--controller", "http://127.0.0.1:9"]
    seen = []
    with patch.object(sys, "argv", sentinel), patch(
        "courier_worker.service.main",
        side_effect=lambda argv: seen.append(argv) or 13,
    ):
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_module("courier_worker.cli", run_name="__main__")
    assert excinfo.value.code == 13
    assert seen == [sentinel]
    assert seen[0] is sentinel
