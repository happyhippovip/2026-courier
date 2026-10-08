"""Dedicated tests for courier_worker.service (Lane L4, Pool Item P9)."""

from courier_worker import service


def test_service_constants():
    assert "TASK_CANCEL_REQUESTED" in service.CANCEL_TYPES
    assert "TASK_CANCELLED" in service.CANCEL_TYPES
    assert service.CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
    assert service.REQUEST_TIMEOUT_S == 10.0
    assert service.STARTUP_HEALTH_ATTEMPTS == 5
    assert service.STARTUP_HEALTH_SLEEP_S == 1.0
    assert service.FLUSH_TIMEOUT_S == 3.0
    assert service.SSE_RECONNECTS == 3
    assert service.SSE_POLL_S == 0.25
