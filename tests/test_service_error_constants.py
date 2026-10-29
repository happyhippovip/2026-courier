"""P9 hardening for courier_worker.service: error hierarchy + timing constants.

Tests only; no behavior change. Pins the offline contract that the other
service P9 aspects do not name: ControllerError hierarchy (ControllerError,
ControllerUnreachable, StaleDispatch), CANCEL_TYPES, and the timing bounds
(REQUEST_TIMEOUT_S, STARTUP_HEALTH_ATTEMPTS, STARTUP_HEALTH_SLEEP_S,
FLUSH_TIMEOUT_S, SSE_RECONNECTS, SSE_POLL_S) plus their wiring as default
arguments. No network calls, no credentials, no filesystem writes.
"""

from __future__ import annotations

import inspect
import math

from courier_worker import service


def test_controller_error_is_runtime_error():
    assert issubclass(service.ControllerError, RuntimeError)


def test_controller_unreachable_is_controller_error():
    assert issubclass(service.ControllerUnreachable, service.ControllerError)
    assert service.ControllerUnreachable is not service.ControllerError


def test_stale_dispatch_is_controller_error():
    assert issubclass(service.StaleDispatch, service.ControllerError)
    assert service.StaleDispatch is not service.ControllerError


def test_unreachable_and_stale_are_distinct():
    assert service.ControllerUnreachable is not service.StaleDispatch
    assert not issubclass(
        service.ControllerUnreachable, service.StaleDispatch
    )
    assert not issubclass(
        service.StaleDispatch, service.ControllerUnreachable
    )


def test_hierarchy_catches_subclasses_as_controller_error():
    for cls in (service.ControllerUnreachable, service.StaleDispatch):
        try:
            raise cls("boom")
        except service.ControllerError as exc:
            assert "boom" in str(exc)
        else:
            raise AssertionError(f"{cls.__name__} not caught as ControllerError")


def test_error_instances_are_exceptions_with_message():
    err = service.ControllerError("down")
    assert isinstance(err, Exception)
    assert str(err) == "down"
    assert isinstance(service.ControllerUnreachable("no controller"), service.ControllerError)
    assert isinstance(service.StaleDispatch("gone"), service.ControllerError)


def test_cancel_types_exact_set():
    assert isinstance(service.CANCEL_TYPES, frozenset)
    assert service.CANCEL_TYPES == frozenset(
        {"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"}
    )


def test_request_timeout_constant():
    assert service.REQUEST_TIMEOUT_S == 10.0
    assert isinstance(service.REQUEST_TIMEOUT_S, float)
    assert math.isfinite(service.REQUEST_TIMEOUT_S)
    assert service.REQUEST_TIMEOUT_S > 0


def test_startup_health_constants():
    assert service.STARTUP_HEALTH_ATTEMPTS == 5
    assert isinstance(service.STARTUP_HEALTH_ATTEMPTS, int)
    assert not isinstance(service.STARTUP_HEALTH_ATTEMPTS, bool)
    assert service.STARTUP_HEALTH_ATTEMPTS >= 1
    assert service.STARTUP_HEALTH_SLEEP_S == 1.0
    assert service.STARTUP_HEALTH_SLEEP_S > 0
    assert math.isfinite(service.STARTUP_HEALTH_SLEEP_S)


def test_flush_timeout_constant():
    assert service.FLUSH_TIMEOUT_S == 3.0
    assert service.FLUSH_TIMEOUT_S > 0
    assert math.isfinite(service.FLUSH_TIMEOUT_S)


def test_sse_constants():
    assert service.SSE_RECONNECTS == 3
    assert isinstance(service.SSE_RECONNECTS, int)
    assert not isinstance(service.SSE_RECONNECTS, bool)
    assert service.SSE_RECONNECTS >= 1
    assert service.SSE_POLL_S == 0.25
    assert 0 < service.SSE_POLL_S < 1.0
    assert math.isfinite(service.SSE_POLL_S)


def test_client_default_timeout_is_request_timeout():
    sig = inspect.signature(service.ControllerClient.__init__)
    assert sig.parameters["timeout_s"].default == service.REQUEST_TIMEOUT_S


def test_flush_outbox_default_timeout_is_flush_timeout():
    sig = inspect.signature(service.WorkerLoop.flush_outbox)
    assert sig.parameters["timeout_s"].default == service.FLUSH_TIMEOUT_S


def test_cancel_watcher_default_timeout_is_request_timeout():
    sig = inspect.signature(service.CancelWatcher.__init__)
    assert sig.parameters["timeout_s"].default == service.REQUEST_TIMEOUT_S
