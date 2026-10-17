"""P9 error-transparency pins for ``courier_worker.cli`` (tests only).

``courier_worker.cli.main`` is an 8-line pass-through to
``courier_worker.service.main``. Sibling open work already pins the happy
paths (argv forwarding, exit-code propagation, ``--help`` / bare / invalid
invocations via subprocess), so this file deliberately covers only the gaps:

- failure transparency: ``RuntimeError``, ``SystemExit`` and
  ``KeyboardInterrupt`` from the delegate propagate unchanged (the wrapper
  never swallows, remaps, or converts them into a success code);
- argv freshness: every call reads the *current* ``sys.argv`` and passes
  that exact list object through (no caching, no silent copy/rewrite);
- signature: ``main()`` takes no arguments.

No behavior change. No network, no subprocess, no credentials; every case
runs in-process with ``monkeypatch`` fixtures.
"""

from __future__ import annotations

import sys

import pytest

import courier_worker.cli as cli


def test_runtime_error_propagates_unchanged(monkeypatch):
    """A delegate failure must surface, never become a success code."""
    boom = RuntimeError("delegate blew up")
    monkeypatch.setattr(cli, "_main", lambda argv: (_ for _ in ()).throw(boom))
    monkeypatch.setattr(sys, "argv", ["courier-worker"])
    with pytest.raises(RuntimeError) as excinfo:
        cli.main()
    assert excinfo.value is boom


def test_system_exit_propagates_with_code(monkeypatch):
    """SystemExit from the delegate is not converted into a return value."""
    monkeypatch.setattr(
        cli, "_main", lambda argv: (_ for _ in ()).throw(SystemExit(7))
    )
    monkeypatch.setattr(sys, "argv", ["courier-worker"])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 7


def test_keyboard_interrupt_propagates(monkeypatch):
    """BaseException transparency: an interrupt never becomes exit 0."""
    monkeypatch.setattr(
        cli, "_main", lambda argv: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    monkeypatch.setattr(sys, "argv", ["courier-worker"])
    with pytest.raises(KeyboardInterrupt):
        cli.main()


def test_argv_read_fresh_on_every_call(monkeypatch):
    """No caching: consecutive calls each observe the current sys.argv."""
    seen = []
    monkeypatch.setattr(cli, "_main", lambda argv: seen.append(argv) or 0)
    first = ["courier-worker", "--controller", "http://127.0.0.1:1111"]
    second = ["courier-worker", "--controller", "http://127.0.0.1:2222"]
    monkeypatch.setattr(sys, "argv", first)
    assert cli.main() == 0
    monkeypatch.setattr(sys, "argv", second)
    assert cli.main() == 0
    assert seen == [first, second]


def test_argv_object_passed_through_unmodified(monkeypatch):
    """The exact sys.argv list object reaches the delegate untouched."""
    seen = []
    monkeypatch.setattr(cli, "_main", lambda argv: seen.append(argv) or 0)
    argv = ["courier-worker", "--max-tasks", "1"]
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 0
    assert len(seen) == 1
    assert seen[0] is argv


def test_main_takes_no_arguments():
    """Signature pin: main() accepts zero parameters."""
    with pytest.raises(TypeError):
        cli.main(["courier-worker"])  # type: ignore[arg-type]
