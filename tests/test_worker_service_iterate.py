"""P9-service_iterate: WorkerLoop.iterate return-contract pins.

Tests only; no behavior change. ``WorkerLoop.iterate`` runs one
claim-execute-deliver cycle and reports what happened as a plain string:
``"idle"``, ``"spec-rejected"``, ``"stale"``, ``"abandoned"`` or
``"delivered"``. These pins lock that contract with a fake controller
client and a stub engine: no network, no threads, no subprocesses.
``CancelWatcher.start`` is stubbed where the cycle would otherwise open a
real SSE socket; ``stop()`` on a never-started watcher is already safe.
"""

from __future__ import annotations

import json
import threading

from courier_worker import adapter_bridge
from courier_worker.host import ExecutionResult, Outcome
from courier_worker.service import (
    CancelWatcher,
    ControllerUnreachable,
    StaleDispatch,
    WorkerLoop,
)


class FakeClient:
    """Offline stand-in for ControllerClient."""

    def __init__(self, claim=None, start_exc=None):
        self.claim_answer = claim
        self.start_exc = start_exc
        self.token = "test-token"
        self.claim_calls = 0
        self.heartbeats = []
        self.delivered = []

    def claim(self, worker_id):
        self.claim_calls += 1
        if isinstance(self.claim_answer, Exception):
            raise self.claim_answer
        return self.claim_answer

    def start(self, dispatch_id):
        if self.start_exc is not None:
            raise self.start_exc
        return None

    def heartbeat(self, worker_id, dispatch_ids):
        self.heartbeats.append((worker_id, list(dispatch_ids)))
        return {}

    def deliver(self, payload):
        self.delivered.append(payload)
        return "accepted"


class StubEngine:
    """Offline stand-in for WorkerHost (only what iterate touches)."""

    def __init__(self, probe=None, result=None):
        self.probe = probe
        self.result = result
        self.run_specs = []

    def _pressure_probe(self):
        return self.probe

    def run_once(self, spec, on_heartbeat=None, is_cancelled=None):
        self.run_specs.append(spec)
        return self.result


def _claim(dispatch_id="d1", **overrides):
    claim = {
        "task_id": "t1",
        "dispatch_id": dispatch_id,
        "attempt": 1,
        "ttl_s": 60,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "ek-1"},
    }
    claim.update(overrides)
    return claim


def _loop(home, client, engine):
    return WorkerLoop(
        home=str(home),
        base_url="http://127.0.0.1:9",
        worker_id="w1",
        heartbeat_s=1.0,
        engine=engine,
        client_factory=lambda: client,
    )


def _stop():
    return threading.Event()


def test_flush_failure_is_idle_without_touching_controller(tmp_path):
    def _boom():
        raise ControllerUnreachable("no controller here")

    loop = WorkerLoop(
        home=str(tmp_path),
        base_url="http://127.0.0.1:9",
        worker_id="w1",
        heartbeat_s=1.0,
        engine=StubEngine(),
        client_factory=_boom,
    )
    assert loop.iterate(_stop()) == "idle"


def test_pressure_skips_claim_and_sends_idle_heartbeat(tmp_path):
    client = FakeClient(claim=_claim())
    loop = _loop(tmp_path, client, StubEngine(probe="HOT"))
    assert loop.iterate(_stop()) == "idle"
    assert client.claim_calls == 0
    assert client.heartbeats == [("w1", [])]
    assert loop._last_resource_state == "PRESSURED"


def test_cooldown_stays_idle_after_pressure_clears(tmp_path):
    client = FakeClient(claim=_claim())
    engine = StubEngine(probe="HOT")
    loop = _loop(tmp_path, client, engine)
    assert loop.iterate(_stop()) == "idle"
    engine.probe = None
    assert loop.iterate(_stop()) == "idle"
    assert client.claim_calls == 0
    assert len(client.heartbeats) == 2
    assert loop._last_resource_state == "COOLDOWN"


def test_no_claim_is_idle_with_heartbeat(tmp_path):
    client = FakeClient(claim=None)
    loop = _loop(tmp_path, client, StubEngine())
    assert loop.iterate(_stop()) == "idle"
    assert client.heartbeats == [("w1", [])]


def test_spec_rejected_delivers_failure_payload(tmp_path):
    client = FakeClient(claim=_claim(dispatch_id="d9", task_id=""))
    loop = _loop(tmp_path, client, StubEngine())
    assert loop.iterate(_stop()) == "spec-rejected"
    assert len(client.delivered) == 1
    payload = client.delivered[0]
    assert payload["dispatch_id"] == "d9"
    assert payload["result_id"] == "r-d9"
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False


def test_stale_start_cleans_up_request_files(tmp_path):
    client = FakeClient(claim=_claim(dispatch_id="d3"), start_exc=StaleDispatch("gone"))
    loop = _loop(tmp_path, client, StubEngine())
    assert loop.iterate(_stop()) == "stale"
    import os

    assert not os.path.exists(adapter_bridge.request_path(str(tmp_path), "d3"))
    assert not os.path.exists(adapter_bridge.report_path(str(tmp_path), "d3"))
    assert client.delivered == []


def test_delivered_success_with_structured_report(tmp_path, monkeypatch):
    monkeypatch.setattr(CancelWatcher, "start", lambda self: None)
    home = str(tmp_path)
    report = {"outcome": "success", "reason": "", "retryable": False}
    import os

    engine = StubEngine()

    def _run_once(spec, on_heartbeat=None, is_cancelled=None):
        engine.run_specs.append(spec)
        # The runner writes its structured report while the host runs the
        # dispatch; write_request deleted any stale report up front, so a
        # report must appear here for the delivery to count as success.
        live_report = adapter_bridge.report_path(home, spec.dispatch_id)
        import os as _os

        _os.makedirs(_os.path.dirname(live_report), exist_ok=True)
        with open(live_report, "w", encoding="utf-8") as fh:
            json.dump(report, fh)
        return ExecutionResult(spec=spec, outcome=Outcome.COMPLETED)

    engine.run_once = _run_once
    client = FakeClient(claim=_claim(dispatch_id="d2"))
    loop = _loop(tmp_path, client, engine)
    assert loop.iterate(_stop()) == "delivered"
    assert len(client.delivered) == 1
    payload = client.delivered[0]
    assert payload["dispatch_id"] == "d2"
    assert payload["result_id"] == "r-d2"
    assert payload["outcome"] == "success"
    assert "retryable" not in payload
    assert not os.path.exists(adapter_bridge.request_path(home, "d2"))
    assert not os.path.exists(adapter_bridge.report_path(home, "d2"))
    assert loop._watchers == {}


def test_abandoned_on_host_shutdown_cancel_reports_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(CancelWatcher, "start", lambda self: None)
    home = str(tmp_path)
    engine = StubEngine()

    def _run_once(spec, on_heartbeat=None, is_cancelled=None):
        engine.run_specs.append(spec)
        return ExecutionResult(spec=spec, outcome=Outcome.CANCELLED)

    engine.run_once = _run_once
    client = FakeClient(claim=_claim(dispatch_id="d4"))
    loop = _loop(tmp_path, client, engine)
    assert loop.iterate(_stop()) == "abandoned"
    assert client.delivered == []
    import os

    assert not os.path.exists(adapter_bridge.request_path(home, "d4"))
    assert loop._watchers == {}
