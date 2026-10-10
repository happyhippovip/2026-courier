"""P9 test hardening for courier_worker.service (failure payload + offline client pins).

Tests only; no behavior change. Pins the offline surface of
:mod:`courier_worker.service`: controller-URL validation, claim / heartbeat /
deliver / start status mapping (via stubbed transport, no network),
``build_spec_failure_payload`` shape, ``_artifact_prefix`` scope math, and
``CancelWatcher._dispatch_event`` matching. No network, no credentials.
"""

from __future__ import annotations

import pytest

from courier_worker.service import (
    CANCEL_TYPES,
    CancelWatcher,
    ControllerClient,
    ControllerError,
    StaleDispatch,
    _artifact_prefix,
    build_spec_failure_payload,
)

BASE_HTTP = "http://example.invalid"
BASE_HTTPS = "https://example.invalid"
PLACEHOLDER = "placeholder"


def _client(base_url=BASE_HTTP):
    return ControllerClient(base_url, PLACEHOLDER)


def _stub(client, status, payload=None, exc=None):
    def _fake(method, path, body=None):
        if exc is not None:
            raise exc
        return status, payload

    client._call = _fake  # noqa: SLF001 - stub transport, no network
    return client


# -- ControllerClient init ----------------------------------------------------


def test_client_rejects_missing_scheme():
    with pytest.raises(ControllerError):
        ControllerClient("example.invalid", PLACEHOLDER)


def test_client_rejects_bad_scheme():
    with pytest.raises(ControllerError):
        ControllerClient("ftp://example.invalid", PLACEHOLDER)


def test_client_rejects_missing_hostname():
    with pytest.raises(ControllerError):
        ControllerClient("http://", PLACEHOLDER)


def test_client_strips_trailing_slash():
    client = _client(BASE_HTTP + "///")
    assert client.base_url == BASE_HTTP


def test_client_keeps_https_and_custom_timeout():
    client = ControllerClient(BASE_HTTPS + "/", PLACEHOLDER, timeout_s=1.5)
    assert client.base_url == BASE_HTTPS
    assert client.timeout_s == 1.5


# -- health / claim mapping (stubbed, no network) ------------------------------


def test_health_true_on_200():
    client = _stub(_client(), 200, {"ok": True})
    assert client.health() is True


def test_health_false_on_non_200():
    client = _stub(_client(), 503, None)
    assert client.health() is False


def test_health_false_when_transport_raises():
    client = _stub(_client(), 200, exc=ControllerError("down"))
    assert client.health() is False


def test_claim_returns_payload_on_200_dict():
    payload = {"task_id": "t1", "dispatch_id": "d1"}
    client = _stub(_client(), 200, payload)
    assert client.claim("w1") == payload


def test_claim_none_on_204():
    client = _stub(_client(), 204, None)
    assert client.claim("w1") is None


def test_claim_none_when_transport_raises():
    client = _stub(_client(), 200, exc=ControllerError("down"))
    assert client.claim("w1") is None


def test_claim_none_on_200_non_dict():
    client = _stub(_client(), 200, ["not", "a", "dict"])
    assert client.claim("w1") is None


def test_claim_none_on_unexpected_status():
    client = _stub(_client(), 400, {"task_id": "t1"})
    assert client.claim("w1") is None


# -- start / heartbeat / deliver mapping ---------------------------------------


def test_start_ok_on_200():
    client = _stub(_client(), 200, None)
    assert client.start("d1") is None


@pytest.mark.parametrize("status", [404, 409])
def test_start_stale_on_gone_statuses(status):
    client = _stub(_client(), status, None)
    with pytest.raises(StaleDispatch):
        client.start("d1")


def test_start_stale_on_other_non_200():
    client = _stub(_client(), 400, None)
    with pytest.raises(StaleDispatch):
        client.start("d1")


def test_start_stale_when_transport_raises():
    client = _stub(_client(), 200, exc=ControllerError("down"))
    with pytest.raises(StaleDispatch):
        client.start("d1")


def test_heartbeat_returns_payload():
    client = _stub(_client(), 200, {"cancel": []})
    assert client.heartbeat("w1", ["d1"]) == {"cancel": []}


def test_heartbeat_empty_payload_becomes_empty_dict():
    client = _stub(_client(), 200, None)
    assert client.heartbeat("w1", []) == {}


def test_heartbeat_raises_on_non_200():
    client = _stub(_client(), 503, None)
    with pytest.raises(ControllerError):
        client.heartbeat("w1", [])


@pytest.mark.parametrize(
    "body",
    [
        {"status": "ACCEPTED_FOR_VERIFY"},
        {"status": "ACK_DUPLICATE"},
        {"status": "SOMETHING_ELSE"},
        {"other": 1},
        None,
    ],
)
def test_deliver_accepted_on_200(body):
    client = _stub(_client(), 200, body)
    assert client.deliver({"dispatch_id": "d1"}) == "accepted"


@pytest.mark.parametrize("status", [404, 409])
def test_deliver_stale_on_gone_statuses(status):
    client = _stub(_client(), status, None)
    assert client.deliver({"dispatch_id": "d1"}) == "stale"


def test_deliver_raises_on_unexpected_status():
    client = _stub(_client(), 400, None)
    with pytest.raises(ControllerError):
        client.deliver({"dispatch_id": "d1"})


def test_deliver_propagates_transport_error():
    client = _stub(_client(), 200, exc=ControllerError("down"))
    with pytest.raises(ControllerError):
        client.deliver({"dispatch_id": "d1"})


# -- build_spec_failure_payload --------------------------------------------------


def test_failure_payload_exact_shape():
    payload = build_spec_failure_payload("d1", "r-d1", "spec-invalid: bad")
    assert payload == {
        "dispatch_id": "d1",
        "result_id": "r-d1",
        "artifacts": [],
        "outcome": "failure",
        "retryable": False,
        "reason": "spec-invalid: bad",
    }


def test_failure_payload_preserves_ids_and_reason():
    payload = build_spec_failure_payload("d-x", "r-d-x", "why")
    assert payload["dispatch_id"] == "d-x"
    assert payload["result_id"] == "r-d-x"
    assert payload["reason"] == "why"
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False


# -- _artifact_prefix ------------------------------------------------------------


def test_artifact_prefix_inside_home(tmp_path):
    artifact_dir = str(tmp_path / "artifacts" / "d1")
    assert _artifact_prefix(artifact_dir, str(tmp_path)) == "artifacts/d1/"


def test_artifact_prefix_outside_home_is_empty(tmp_path):
    artifact_dir = str(tmp_path / "artifacts" / "d1")
    other = str(tmp_path / "elsewhere")
    assert _artifact_prefix(artifact_dir, other) == ""


def test_artifact_prefix_no_home_is_empty(tmp_path):
    artifact_dir = str(tmp_path / "artifacts" / "d1")
    assert _artifact_prefix(artifact_dir, None) == ""


def test_artifact_prefix_same_dir_is_empty(tmp_path):
    assert _artifact_prefix(str(tmp_path), str(tmp_path)) == ""


# -- CancelWatcher._dispatch_event -------------------------------------------------


def _watcher(task_id="t1"):
    return CancelWatcher(BASE_HTTP, PLACEHOLDER, task_id)


def test_cancel_types_cover_both_values():
    assert CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})


def test_dispatch_empty_lines_never_cancels():
    watcher = _watcher()
    watcher._dispatch_event([])  # noqa: SLF001 - pure dispatch, no network
    assert watcher.cancelled() is False


def test_dispatch_bad_json_never_cancels():
    watcher = _watcher()
    watcher._dispatch_event(["not json"])  # noqa: SLF001
    assert watcher.cancelled() is False


def test_dispatch_non_dict_never_cancels():
    watcher = _watcher()
    watcher._dispatch_event(['["a", "list"]'])  # noqa: SLF001
    assert watcher.cancelled() is False


@pytest.mark.parametrize("event_type", ["TASK_CANCEL_REQUESTED", "TASK_CANCELLED"])
def test_dispatch_matching_cancel_sets_flag(event_type):
    watcher = _watcher("t1")
    watcher._dispatch_event([f'{{"type": "{event_type}", "task_id": "t1"}}'])  # noqa: SLF001
    assert watcher.cancelled() is True


def test_dispatch_wrong_task_id_does_not_cancel():
    watcher = _watcher("t1")
    watcher._dispatch_event(['{"type": "TASK_CANCELLED", "task_id": "t2"}'])  # noqa: SLF001
    assert watcher.cancelled() is False


def test_dispatch_non_cancel_type_does_not_cancel():
    watcher = _watcher("t1")
    watcher._dispatch_event(['{"type": "TASK_STARTED", "task_id": "t1"}'])  # noqa: SLF001
    assert watcher.cancelled() is False


def test_dispatch_nested_payload_match_sets_flag():
    watcher = _watcher("t9")
    watcher._dispatch_event(['{"payload": {"type": "TASK_CANCELLED", "task_id": "t9"}}'])  # noqa: SLF001
    assert watcher.cancelled() is True


def test_dispatch_event_type_alias_match_sets_flag():
    watcher = _watcher("t1")
    watcher._dispatch_event(['{"event_type": "TASK_CANCEL_REQUESTED", "task_id": "t1"}'])  # noqa: SLF001
    assert watcher.cancelled() is True
