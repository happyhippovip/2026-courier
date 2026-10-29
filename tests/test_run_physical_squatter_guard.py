"""Squatter guard for the physical runner (scripts/run_physical.py).

If a foreign (possibly stale) service holds the port, it answers health
checks and accepts goals, which previously surfaced as a misleading
FALSIFIED: central_state.json missing. The runner must refuse instead of
submitting goals to that stranger.
"""
import shutil
import socket
import subprocess
import sys
import time

import pytest

import scripts.run_physical as script

needs_lsof = pytest.mark.skipif(
    shutil.which("lsof") is None, reason="listener check needs lsof")


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_listening(port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


_LISTEN_SNIPPET = (
    "import socket, time; s = socket.socket(); "
    "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); "
    "s.bind(('127.0.0.1', %d)); s.listen(1); time.sleep(60)"
)


def test_dead_server_process_refuses():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    assert proc.poll() is not None
    with pytest.raises(RuntimeError, match="refusing to run"):
        script.assert_server_ownership(proc, _free_port())


def test_no_process_passes():
    script.assert_server_ownership(None, _free_port())  # must not raise


@needs_lsof
def test_stranger_holding_port_refuses():
    port = _free_port()
    stranger = subprocess.Popen(
        [sys.executable, "-c", _LISTEN_SNIPPET % port])
    ours = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert _wait_listening(port), "stranger never started listening"
        assert ours.poll() is None
        with pytest.raises(RuntimeError, match="held by another process"):
            script.assert_server_ownership(ours, port)
    finally:
        for proc in (stranger, ours):
            proc.kill()
            proc.wait(timeout=30)


@needs_lsof
def test_own_server_process_passes():
    port = _free_port()
    owner = subprocess.Popen(
        [sys.executable, "-c", _LISTEN_SNIPPET % port])
    try:
        assert _wait_listening(port), "owner never started listening"
        script.assert_server_ownership(owner, port)  # must not raise
    finally:
        owner.kill()
        owner.wait(timeout=30)
