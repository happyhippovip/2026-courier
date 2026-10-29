"""P9 hardening pins for courier_worker.service run() shutdown contract.

Tests only: no behavior change. Pins the WorkerLoop.run() exit-code mapping
that is not covered by any open P9-service PR branch (checked all in-flight
``test_worker_service_*`` / ``test_courier_worker_service`` / ``test_p9_service_*``
files): a final outbox flush that leaves undelivered results exits 1, while a
drained flush (including a stale-answer drain) exits 0; and a ControllerError
raised by the loop body degrades to idle without killing the loop.

Offline: controller health/deliver are monkeypatched; no network calls and no
real credentials (a dummy token file is written only so _default_client can
be constructed).
"""

import threading

from courier_worker.host import outbox_write
from courier_worker.service import (
    ControllerClient,
    ControllerError,
    WorkerLoop,
)


def _write_token(home) -> None:
    run_dir = home / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "controller.token").write_text("test-token", encoding="utf-8")


def _make_loop(home, monkeypatch, deliver):
    _write_token(home)
    monkeypatch.setattr(ControllerClient, "health", lambda self: True)
    monkeypatch.setattr(ControllerClient, "deliver", deliver)
    return WorkerLoop(str(home), "http://127.0.0.1:9/", "w-1", 0.05)


def test_run_returns_one_when_final_flush_leaves_results_undelivered(tmp_path, monkeypatch):
    def _down(self, payload):
        raise ControllerError("controller down")

    loop = _make_loop(tmp_path, monkeypatch, _down)
    outbox_write(str(tmp_path), {"dispatch_id": "d-1", "result_id": "r-d-1"})
    stop = threading.Event()
    stop.set()
    assert loop.run(stop) == 1


def test_run_returns_zero_when_final_flush_drains_stale_answer(tmp_path, monkeypatch):
    def _stale(self, payload):
        return "stale"

    loop = _make_loop(tmp_path, monkeypatch, _stale)
    outbox_write(str(tmp_path), {"dispatch_id": "d-1", "result_id": "r-d-1"})
    stop = threading.Event()
    stop.set()
    assert loop.run(stop) == 0


def test_run_treats_loop_controller_error_as_idle_and_continues(tmp_path, monkeypatch):
    loop = _make_loop(
        tmp_path, monkeypatch, lambda self, payload: (_ for _ in ()).throw(
            AssertionError("deliver must not run with an empty outbox")))
    calls = []

    def _flaky_iterate(stop):
        calls.append(1)
        if len(calls) == 1:
            raise ControllerError("transient loop failure")
        stop.set()
        return "idle"

    monkeypatch.setattr(loop, "iterate", _flaky_iterate)
    assert loop.run(threading.Event()) == 0
    assert len(calls) == 2
