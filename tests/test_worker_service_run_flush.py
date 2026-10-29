"""P9 test hardening for courier_worker.service (P9-service_runloop).

Tests only; no behavior change. No network, no subprocess, no credentials:
every controller interaction goes through a small in-process fake and all
state lives under tmp_path.

Module under test: courier_worker/service.py -- WorkerLoop.run() startup and
shutdown lifecycle plus WorkerLoop.flush_outbox() drain semantics. Sibling
open work pins the client methods, resolve_spec, result payloads, argv
handling, the cancel watcher and _deliver_payload; this file deliberately
covers only the gaps:

- run() with an already-set stop event returns 0 without ever claiming;
- run() against a persistently unhealthy controller raises
  ControllerUnreachable without leaking the token value in the message;
- flush_outbox() drains accepted and stale answers and reports 0 remaining;
- flush_outbox() keeps undeliverable payloads queued and reports them.
"""

from __future__ import annotations

import threading

import pytest

from courier_worker import service
from courier_worker.host import outbox_read_all, outbox_write


class _FakeClient:
    """In-process stand-in for ControllerClient. No sockets, no threads."""

    def __init__(self, healthy=True, token="test-token-not-a-secret"):
        self.healthy = healthy
        self.token = token
        self.health_calls = 0
        self.claim_calls = 0
        self.deliver_calls = []
        self.deliver_behavior = "accepted"

    def health(self):
        self.health_calls += 1
        return self.healthy

    def claim(self, worker_id):
        self.claim_calls += 1
        return None

    def deliver(self, payload):
        self.deliver_calls.append(payload)
        if isinstance(self.deliver_behavior, Exception):
            raise self.deliver_behavior
        return self.deliver_behavior


def _loop(tmp_path, fake, heartbeat_s=0.2):
    loop = service.WorkerLoop(
        str(tmp_path), "http://127.0.0.1:9", "worker-test",
        heartbeat_s, client_factory=lambda: fake,
    )
    return loop


def test_run_with_preset_stop_returns_zero_without_claiming(tmp_path, monkeypatch):
    fake = _FakeClient(healthy=True)
    loop = _loop(tmp_path, fake)
    monkeypatch.setattr(loop, "_default_client", lambda: fake)
    stop = threading.Event()
    stop.set()
    assert loop.run(stop) == 0
    assert fake.health_calls >= 1
    assert fake.claim_calls == 0


def test_run_with_unhealthy_controller_raises_without_token_leak(tmp_path, monkeypatch):
    fake = _FakeClient(healthy=False, token="test-token-not-a-secret")
    loop = _loop(tmp_path, fake)
    monkeypatch.setattr(loop, "_default_client", lambda: fake)
    monkeypatch.setattr(service, "STARTUP_HEALTH_SLEEP_S", 0)
    with pytest.raises(service.ControllerUnreachable) as excinfo:
        loop.run()
    assert "http://127.0.0.1:9" in str(excinfo.value)
    assert "test-token-not-a-secret" not in str(excinfo.value)
    assert fake.claim_calls == 0


def test_flush_outbox_drains_accepted_and_returns_zero(tmp_path):
    fake = _FakeClient()
    loop = _loop(tmp_path, fake)
    payload = {"dispatch_id": "d-1", "result_id": "r-d-1", "outcome": "success"}
    outbox_write(str(tmp_path), payload)
    assert loop.flush_outbox() == 0
    assert fake.deliver_calls == [payload]
    assert outbox_read_all(str(tmp_path)) == []


def test_flush_outbox_drains_stale_answer(tmp_path):
    fake = _FakeClient()
    fake.deliver_behavior = "stale"
    loop = _loop(tmp_path, fake)
    outbox_write(str(tmp_path), {"dispatch_id": "d-2", "result_id": "r-d-2"})
    assert loop.flush_outbox() == 0
    assert outbox_read_all(str(tmp_path)) == []


def test_flush_outbox_keeps_undeliverable_and_counts_remaining(tmp_path):
    fake = _FakeClient()
    fake.deliver_behavior = service.ControllerError("controller down")
    loop = _loop(tmp_path, fake)
    payload = {"dispatch_id": "d-3", "result_id": "r-d-3", "outcome": "success"}
    outbox_write(str(tmp_path), payload)
    assert loop.flush_outbox() == 1
    remaining = outbox_read_all(str(tmp_path))
    assert len(remaining) == 1
    assert remaining[0][1]["dispatch_id"] == "d-3"


def test_flush_outbox_empty_reports_zero(tmp_path):
    fake = _FakeClient()
    loop = _loop(tmp_path, fake)
    assert loop.flush_outbox() == 0
    assert fake.deliver_calls == []
