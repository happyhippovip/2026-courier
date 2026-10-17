"""Packaged Windows cancel watcher must release a silent SSE stream on stop.

The copy under scripts/windows_worker/dist still blocks in http.client
readline for timeout_s. integration/v1's courier_worker.service already polls
the socket, so stop() can join the watcher. A stuck watcher holds the socket
after the unit that opened it has finished.
"""

import importlib.util
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGED_SERVICE = ROOT / "scripts" / "windows_worker" / "dist" / "courier_worker" / "service.py"


def _load_packaged_service():
    spec = importlib.util.spec_from_file_location(
        "packaged_windows_courier_service", PACKAGED_SERVICE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S = _load_packaged_service()


def _silent_sse(bound):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    bound.append(listener.getsockname()[1])
    listener.settimeout(10)
    try:
        conn, _addr = listener.accept()
    except socket.timeout:
        listener.close()
        return
    try:
        data = b""
        conn.settimeout(5)
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk
        conn.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n")
        conn.settimeout(15)
        while True:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
    finally:
        try:
            conn.close()
        except OSError:
            pass
        listener.close()


def test_stop_releases_a_silent_packaged_event_stream():
    bound = []
    server = threading.Thread(target=_silent_sse, args=(bound,), daemon=True)
    server.start()
    deadline = time.monotonic() + 2
    while not bound and time.monotonic() < deadline:
        time.sleep(0.01)
    assert bound, "silent SSE server did not bind"
    watcher = S.CancelWatcher(
        f"http://127.0.0.1:{bound[0]}", "token", "t-quiet", timeout_s=8.0)
    watcher.start()
    time.sleep(0.4)
    thread = watcher._thread
    assert thread.is_alive()
    started = time.monotonic()
    watcher.stop()
    elapsed = time.monotonic() - started
    assert elapsed < 1.5
    assert not thread.is_alive()
    assert not watcher.degraded
