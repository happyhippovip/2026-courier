"""Targeted test: watchdog single reclaim poll.

- run_once returns counts on success and never raises on transport,
  HTTP-error, or malformed-body failures (next poll retries).
- Non-200 responses are logged, not silently swallowed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import courier_watchdog as watchdog


class FakeResponse:
    def __init__(self, status_code, payload=None, explode=False):
        self.status_code = status_code
        self._payload = payload
        self._explode = explode

    def json(self):
        if self._explode:
            raise ValueError("not json")
        return self._payload or {}


def test_run_once_success(monkeypatch):
    monkeypatch.setattr(
        watchdog.requests, "post",
        lambda *a, **k: FakeResponse(200, {"reclaimed_tasks": 2, "quarantined_tasks": 1}))
    assert watchdog.run_once() == (2, 1)


def test_run_once_non_200_logs_and_returns_zeros(monkeypatch, capsys):
    monkeypatch.setattr(
        watchdog.requests, "post", lambda *a, **k: FakeResponse(503))
    assert watchdog.run_once() == (0, 0)
    assert "503" in capsys.readouterr().out


def test_run_once_bad_body_never_raises(monkeypatch):
    monkeypatch.setattr(
        watchdog.requests, "post", lambda *a, **k: FakeResponse(200, explode=True))
    assert watchdog.run_once() == (0, 0)


def test_run_once_transport_error_never_raises(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("down")
    monkeypatch.setattr(watchdog.requests, "post", boom)
    assert watchdog.run_once() == (0, 0)
