"""Offline pins for CancelWatcher lifecycle (courier_worker.service).

Scope: construction defaults, start/stop thread handling, and the
reconnect bound in _follow. Everything here runs with no socket and no
server: socket.create_connection always raises, or _subscribe is stubbed.

Complements the live-stub coverage in tests/test_l3_worker_host.py
(stop releases a blocked stream; a rejected subscription degrades) and
the _dispatch_event pins in flight elsewhere: no assertion here overlaps
those paths.
"""

import socket

from courier_worker import service as S


class _InstantStop:
    """Minimal stand-in for the watcher's stop event; wait() never sleeps."""

    def __init__(self):
        self._flag = False
        self.waits = 0

    def is_set(self):
        return self._flag

    def set(self):
        self._flag = True

    def wait(self, timeout=None):
        self.waits += 1
        return self._flag


def _refuse_connections(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("connection refused (offline pin)")

    monkeypatch.setattr(socket, "create_connection", _raise)


def _watcher(**kwargs):
    return S.CancelWatcher("http://controller.invalid", "tok", "t-1", **kwargs)


def test_init_defaults_are_untriggered():
    watcher = _watcher()
    assert watcher.timeout_s == S.REQUEST_TIMEOUT_S
    assert watcher.task_id == "t-1"
    assert watcher.cancelled() is False
    assert watcher.degraded is False
    assert watcher._thread is None


def test_init_honours_custom_timeout():
    watcher = _watcher(timeout_s=2.5)
    assert watcher.timeout_s == 2.5


def test_stop_before_start_is_safe():
    watcher = _watcher()
    watcher.stop()  # no thread yet; must not raise
    assert watcher._thread is None
    assert watcher.cancelled() is False


def test_start_spawns_daemon_watch_thread_then_stop_joins(monkeypatch):
    _refuse_connections(monkeypatch)  # _subscribe fails fast; no network
    watcher = _watcher()
    watcher.start()
    thread = watcher._thread
    assert thread is not None
    assert thread.daemon is True
    assert thread.name == "courier-cancel-watch"
    watcher.stop()
    assert watcher._thread is None
    assert not thread.is_alive()
    assert watcher.cancelled() is False
    assert watcher.degraded is False


def test_follow_gives_up_after_reconnect_bound(monkeypatch):
    _refuse_connections(monkeypatch)
    watcher = _watcher()
    stop = _InstantStop()
    monkeypatch.setattr(watcher, "_stop", stop)
    calls = {"n": 0}
    original_subscribe = watcher._subscribe

    def counting_subscribe():
        calls["n"] += 1
        return original_subscribe()

    monkeypatch.setattr(watcher, "_subscribe", counting_subscribe)
    watcher._follow()
    assert calls["n"] == S.SSE_RECONNECTS + 1
    assert stop.waits == S.SSE_RECONNECTS
    assert watcher.degraded is True
    assert watcher.cancelled() is False


def test_follow_clean_eof_returns_without_degrading(monkeypatch):
    watcher = _watcher()
    stop = _InstantStop()
    monkeypatch.setattr(watcher, "_stop", stop)
    calls = {"n": 0}

    def clean_eof():
        calls["n"] += 1
        return None

    monkeypatch.setattr(watcher, "_subscribe", clean_eof)
    watcher._follow()
    assert calls["n"] == 1
    assert stop.waits == 0
    assert watcher.degraded is False
    assert watcher.cancelled() is False
