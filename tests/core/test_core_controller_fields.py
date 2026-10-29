"""Field-contract hardening for courier_core.controller (P9-controller_fields).

Covers only the pure request-field contracts: TASK_FIELDS / RESULT_FIELDS /
RESOLVE_DECISIONS shapes, the _only_fields / _require_id / _require_int /
_require_reason validators, heartbeat_interval bounds, ApiError.body and the
numeric limit constants. No journal, no DB, no network, no behavior change.

Overlap note: #345 hardens courier_core.controller broadly via
tests/core/test_core_controller.py; this file uses a separate filename and
does not touch that file.
"""

from __future__ import annotations

import pytest

from courier_core.controller import (
    MAX_ARTIFACTS,
    MAX_HEARTBEAT_DISPATCHES,
    MAX_ID_LENGTH,
    MAX_LEASE_TTL_S,
    MAX_REASON_CHARS,
    MAX_TIMEOUT_S,
    RESOLVE_DECISIONS,
    RESULT_FIELDS,
    SUSPEND_GAP_S,
    TASK_FIELDS,
    ApiError,
    Lease,
    _only_fields,
    _require_id,
    _require_int,
    _require_reason,
    heartbeat_interval,
)
from courier_core.events import MAX_ATTEMPTS_LIMIT, EventType


def test_task_fields_exact_set():
    assert TASK_FIELDS == {
        "adapter",
        "params",
        "effect_class",
        "max_attempts",
        "lease_ttl_s",
        "timeout_s",
        "idempotency_key",
    }


def test_result_fields_exact_set():
    assert RESULT_FIELDS == {
        "dispatch_id",
        "result_id",
        "artifacts",
        "outcome",
        "retryable",
        "reason",
    }


def test_resolve_decisions_map_to_event_types():
    assert set(RESOLVE_DECISIONS) == {"effect_confirmed", "retry_authorized", "cancel"}
    assert RESOLVE_DECISIONS["effect_confirmed"] is EventType.EFFECT_CONFIRMED
    assert RESOLVE_DECISIONS["retry_authorized"] is EventType.RETRY_AUTHORIZED
    assert RESOLVE_DECISIONS["cancel"] is EventType.TASK_CANCELLED
    assert "bogus" not in RESOLVE_DECISIONS


def test_only_fields_accepts_allowed():
    body = {"worker_id": "w1"}
    assert _only_fields(body, {"worker_id"}) == body
    assert _only_fields({}, {"worker_id"}) == {}


def test_only_fields_rejects_unknown():
    with pytest.raises(ApiError) as exc:
        _only_fields({"worker_id": "w1", "admin": True}, {"worker_id"})
    assert exc.value.status == 400
    assert exc.value.code == "invalid_request"
    assert "admin" in exc.value.message


@pytest.mark.parametrize("bad", [None, [], "x", 42, True])
def test_only_fields_rejects_non_dict(bad):
    with pytest.raises(ApiError) as exc:
        _only_fields(bad, {"worker_id"})
    assert exc.value.status == 400


def test_require_id_ok_and_boundary():
    assert _require_id({"worker_id": "w1"}, "worker_id") == "w1"
    edge = "a" * MAX_ID_LENGTH
    assert _require_id({"worker_id": edge}, "worker_id") == edge


@pytest.mark.parametrize("bad", ["", "a" * (MAX_ID_LENGTH + 1), None, 42, ["w"], {"w": 1}])
def test_require_id_rejects(bad):
    with pytest.raises(ApiError) as exc:
        _require_id({"worker_id": bad}, "worker_id")
    assert exc.value.status == 400


def test_require_int_ok_and_inclusive_bounds():
    assert _require_int({"n": 1}, "n", 1, 100) == 1
    assert _require_int({"n": 100}, "n", 1, 100) == 100
    assert _require_int({}, "n", 1, 100, required=False) is None


@pytest.mark.parametrize("bad", [0, 101, "5", 5.0, True, False, None])
def test_require_int_rejects(bad):
    with pytest.raises(ApiError) as exc:
        _require_int({"n": bad}, "n", 1, 100)
    assert exc.value.status == 400


def test_require_int_missing_required_rejects():
    with pytest.raises(ApiError):
        _require_int({}, "n", 1, 100)


def test_require_reason_optional_missing():
    assert _require_reason({}, required=False) is None


def test_require_reason_ok_and_boundary():
    assert _require_reason({"reason": "hello"}, required=True) == "hello"
    edge = "r" * MAX_REASON_CHARS
    assert _require_reason({"reason": edge}, required=True) == edge


@pytest.mark.parametrize("bad", ["", "   ", "r" * (MAX_REASON_CHARS + 1), None, 42, ["r"]])
def test_require_reason_rejects(bad):
    with pytest.raises(ApiError) as exc:
        _require_reason({"reason": bad}, required=True)
    assert exc.value.status == 400


def test_heartbeat_interval_bounds():
    assert heartbeat_interval(3) == pytest.approx(1.0)
    assert heartbeat_interval(1) == pytest.approx(0.5)
    assert heartbeat_interval(30) == pytest.approx(10.0)
    assert heartbeat_interval(MAX_LEASE_TTL_S) == pytest.approx(MAX_LEASE_TTL_S / 3.0)


def test_api_error_body_carries_extras():
    err = ApiError(409, "stale_dispatch", "old news", task_status="FAILED")
    assert str(err) == "old news"
    assert err.body() == {
        "error": "stale_dispatch",
        "message": "old news",
        "task_status": "FAILED",
    }
    fallback = ApiError(400, "invalid_request")
    assert str(fallback) == "invalid_request"
    assert fallback.body()["message"] == "invalid_request"


def test_numeric_limits():
    assert MAX_LEASE_TTL_S == 3600
    assert MAX_TIMEOUT_S == 7 * 24 * 3600
    assert MAX_HEARTBEAT_DISPATCHES == 256
    assert MAX_ARTIFACTS == 1000
    assert MAX_REASON_CHARS == 2000
    assert MAX_ID_LENGTH == 200
    assert MAX_ATTEMPTS_LIMIT == 100
    assert SUSPEND_GAP_S == pytest.approx(5.0)


def test_lease_dataclass_shape():
    lease = Lease(
        task_id="t1",
        dispatch_id="d1",
        worker_id="w1",
        ttl_s=60,
        deadline=1000.0 + 60,
        reason="ttl",
    )
    assert lease.task_id == "t1"
    assert lease.dispatch_id == "d1"
    assert lease.worker_id == "w1"
    assert lease.ttl_s == 60
    assert lease.reason == "ttl"
