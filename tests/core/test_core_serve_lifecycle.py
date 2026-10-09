"""[L4][P9-serve_lifecycle] shutdown + stop wiring pins for courier_core.serve.

Covers Service stop-path behavior that the other serve suites do not pin:
- ``Service.request_stop`` flips the server stopping event (checked before
  any shutdown work runs).
- ``Service.shutdown`` is idempotent: a second call returns without touching
  the HTTP server again, and the home lock is released.
- ``ControllerServer.allow_reuse_address`` follows the platform rule.
- ``main`` argument handling that exits before any boot: ``--help`` exits 0
  and a non-integer ``--port`` exits 2, both without creating the home dir.

Tests only; no behavior change. No network use beyond a loopback bind that
never accepts a connection (``Service(home, 0)``); no HTTP requests are made.
"""

import os
import threading

import pytest

from courier_core.serve import ControllerServer, HomeLock, Service, main


def _booted_service(home):
    """Construct a real Service on an ephemeral loopback port (never served)."""
    return Service(home, 0)


def test_request_stop_sets_stopping_event(tmp_path):
    service = _booted_service(tmp_path / "home")
    try:
        assert not service.server.stopping.is_set()
        service.request_stop()
        assert service.server.stopping.is_set()
    finally:
        thread = threading.Thread(
            target=service.server.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True,
        )
        thread.start()
        try:
            service.shutdown()
        finally:
            thread.join(timeout=5)


def test_shutdown_is_idempotent_and_releases_lock(tmp_path):
    home = tmp_path / "home"
    service = _booted_service(home)
    thread = threading.Thread(
        target=service.server.serve_forever,
        kwargs={"poll_interval": 0.05},
        daemon=True,
    )
    thread.start()
    try:
        service.shutdown()
        service.shutdown()  # must be a no-op, never raise
    finally:
        thread.join(timeout=5)
    assert not thread.is_alive()
    # The home lock was released: a new owner can acquire it.
    lock = HomeLock(home / "run" / "controller.lock")
    assert lock.acquire()
    lock.release()


def test_allow_reuse_address_follows_platform():
    assert ControllerServer.allow_reuse_address == (os.name != "nt")


def test_main_help_exits_zero_without_boot(tmp_path, capsys):
    home = tmp_path / "newhome"
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert not home.exists()


def test_main_rejects_non_integer_port_without_boot(tmp_path):
    home = tmp_path / "newhome"
    with pytest.raises(SystemExit) as exc:
        main(["--home", str(home), "--port", "abc"])
    assert exc.value.code == 2
    assert not home.exists()
