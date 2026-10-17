"""P9 pins for courier_worker.service: client init + errors (offline only).

Tests only; no behavior change. No network calls: only ControllerClient
__init__ (pure URL parse), error hierarchy, pure payload/prefix helpers,
and constant bounds are exercised. No sockets are opened.
"""

import os

import pytest

from courier_worker.service import (
    CANCEL_TYPES,
    FLUSH_TIMEOUT_S,
    REQUEST_TIMEOUT_S,
    SSE_POLL_S,
    SSE_RECONNECTS,
    ControllerClient,
    ControllerError,
    ControllerUnreachable,
    StaleDispatch,
    _artifact_prefix,
    build_spec_failure_payload,
)


def test_error_hierarchy():
    assert issubclass(ControllerUnreachable, ControllerError)
    assert issubclass(StaleDispatch, ControllerError)
    assert issubclass(ControllerError, RuntimeError)


def test_errors_catch_as_controller_error():
    with pytest.raises(ControllerError):
        raise ControllerUnreachable("boom")
    with pytest.raises(ControllerError):
        raise StaleDispatch("gone")


def test_client_rejects_missing_scheme():
    with pytest.raises(ControllerError):
        ControllerClient("127.0.0.1:8080", "t")


def test_client_rejects_non_http_scheme():
    with pytest.raises(ControllerError):
        ControllerClient("ftp://127.0.0.1/", "t")


def test_client_rejects_missing_host():
    for bad in ("", "not-a-url", "http://", "https://"):
        with pytest.raises(ControllerError):
            ControllerClient(bad, "t")


def test_client_accepts_http_and_strips_trailing_slash():
    client = ControllerClient("http://127.0.0.1:8080///", "tok")
    assert client.base_url == "http://127.0.0.1:8080"
    assert client.token == "tok"
    assert client.timeout_s == REQUEST_TIMEOUT_S


def test_client_accepts_https_with_custom_timeout():
    client = ControllerClient("https://127.0.0.1/", "tok", timeout_s=2.5)
    assert client.base_url == "https://127.0.0.1"
    assert client.timeout_s == 2.5


def test_client_init_does_not_connect():
    # Unroutable port but __init__ only parses; instant offline success.
    client = ControllerClient("http://127.0.0.1:9/", "tok")
    assert client.base_url == "http://127.0.0.1:9"


def test_build_spec_failure_payload_shape():
    payload = build_spec_failure_payload("d-1", "r-d-1", "nope")
    assert payload == {
        "dispatch_id": "d-1",
        "result_id": "r-d-1",
        "artifacts": [],
        "outcome": "failure",
        "retryable": False,
        "reason": "nope",
    }


def test_artifact_prefix_empty_home():
    assert _artifact_prefix("/anything", None) == ""
    assert _artifact_prefix("/anything", "") == ""


def test_artifact_prefix_inside_and_outside(tmp_path):
    home = str(tmp_path)
    inside = os.path.join(home, "artifacts", "d1")
    assert _artifact_prefix(inside, home) == "artifacts/d1/"
    assert _artifact_prefix(home, home) == ""
    assert _artifact_prefix(str(tmp_path.parent), home) == ""


def test_cancel_types():
    assert CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})


def test_timeout_constants_positive():
    assert REQUEST_TIMEOUT_S > 0
    assert FLUSH_TIMEOUT_S > 0
    assert SSE_POLL_S > 0
    assert SSE_RECONNECTS >= 1
