"""P9 hardening for courier_worker.service: pure units only, no network.

Covers ControllerClient URL validation and response mapping (with a fake
connection, never a real socket), resolve_spec fail-closed mapping,
artifact prefixing, result payload shaping, spec-failure payload shape,
and CancelWatcher event dispatch. No behavior change; no network calls.
"""

import http.client
import json

import pytest

from courier_worker import service
from courier_worker.host import ArtifactRef, ExecutionResult, ExecutionSpec, Outcome, SpecError


FAKE_TOKEN = "tok-test"


def _spec(**overrides):
    base = {
        "task_id": "task-1",
        "attempt": 1,
        "dispatch_id": "d-1",
        "worker_id": "worker-1",
        "result_id": "r-d-1",
        "argv": ("python", "runner", "req"),
        "timeout_s": 5.0,
        "lease_ttl_s": 10.0,
        "artifact_dir": "artifacts/d-1",
        "heartbeat_s": 2.0,
    }
    base.update(overrides)
    return ExecutionSpec(**base)


def _result(outcome=Outcome.COMPLETED, artifacts=(), **overrides):
    kwargs = {"spec": _spec(), "outcome": outcome, "artifacts": tuple(artifacts)}
    kwargs.update(overrides)
    return ExecutionResult(**kwargs)


# -- ControllerClient init ---------------------------------------------------

def test_client_rejects_missing_scheme():
    with pytest.raises(service.ControllerError):
        service.ControllerClient("notaurl", FAKE_TOKEN)


def test_client_rejects_empty_url():
    with pytest.raises(service.ControllerError):
        service.ControllerClient("", FAKE_TOKEN)


def test_client_rejects_non_http_scheme():
    with pytest.raises(service.ControllerError):
        service.ControllerClient("ftp://127.0.0.1/x", FAKE_TOKEN)


def test_client_rejects_missing_host():
    with pytest.raises(service.ControllerError):
        service.ControllerClient("http:///nohost", FAKE_TOKEN)


def test_client_accepts_http_and_strips_slash():
    client = service.ControllerClient("http://127.0.0.1:8080/", FAKE_TOKEN)
    assert client.base_url == "http://127.0.0.1:8080"
    assert client.token == FAKE_TOKEN


def test_client_accepts_https():
    client = service.ControllerClient("https://127.0.0.1:8443/api", FAKE_TOKEN, timeout_s=2.5)
    assert client.base_url == "https://127.0.0.1:8443/api"
    assert client.timeout_s == 2.5


# -- ControllerClient._call with fake connection ------------------------------

class _FakeResp:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return self._body


class _FakeConn:
    def __init__(self, resp=None, error=None):
        self.resp = resp
        self.error = error
        self.seen = {}

    def request(self, method, path, body=None, headers=None):
        self.seen = {"method": method, "path": path, "body": body, "headers": headers}
        if self.error is not None:
            raise self.error

    def getresponse(self):
        return self.resp

    def close(self):
        pass


def _client_with_conn(conn):
    client = service.ControllerClient("http://127.0.0.1:9", FAKE_TOKEN)
    client._conn = lambda: conn
    return client


def test_call_sends_token_header_and_path_prefix():
    conn = _FakeConn(_FakeResp(200, b'{"ok": true}'))
    client = _client_with_conn(conn)
    status, payload = client._call("GET", "/health")
    assert status == 200
    assert payload == {"ok": True}
    assert conn.seen["path"] == "/v1/health"
    assert conn.seen["headers"]["X-Courier-Token"] == FAKE_TOKEN


def test_call_raises_on_5xx():
    conn = _FakeConn(_FakeResp(503, b"{}"))
    with pytest.raises(service.ControllerError):
        _client_with_conn(conn)._call("GET", "/health")


def test_call_raises_on_connection_error():
    conn = _FakeConn(error=OSError("down"))
    with pytest.raises(service.ControllerError):
        _client_with_conn(conn)._call("GET", "/health")


def test_call_raises_on_http_exception():
    conn = _FakeConn(error=http.client.HTTPException("bad"))
    with pytest.raises(service.ControllerError):
        _client_with_conn(conn)._call("GET", "/health")


def test_call_invalid_json_gives_none_payload():
    conn = _FakeConn(_FakeResp(200, b"not json"))
    status, payload = _client_with_conn(conn)._call("GET", "/health")
    assert status == 200
    assert payload is None


def test_call_empty_body_gives_none_payload():
    conn = _FakeConn(_FakeResp(204, b""))
    status, payload = _client_with_conn(conn)._call("GET", "/health")
    assert status == 204
    assert payload is None


# -- health / claim / start / heartbeat / deliver -----------------------------

def _stub_client(mapping=None, error=None):
    client = service.ControllerClient("http://127.0.0.1:9", FAKE_TOKEN)

    def fake_call(method, path, body=None):
        if error is not None:
            raise error
        return mapping(method, path, body)

    client._call = fake_call
    return client


def test_health_true_on_200():
    client = _stub_client(lambda m, p, b: (200, {}))
    assert client.health() is True


def test_health_false_on_non_200():
    client = _stub_client(lambda m, p, b: (500, {}))
    # 500 via _call stub returns directly (no raise here); health is False
    assert client.health() is False


def test_health_false_on_error():
    client = _stub_client(error=service.ControllerError("down"))
    assert client.health() is False


def test_claim_returns_payload_on_200_dict():
    client = _stub_client(lambda m, p, b: (200, {"task_id": "t"}))
    assert client.claim("w-1") == {"task_id": "t"}


def test_claim_none_on_204():
    client = _stub_client(lambda m, p, b: (204, None))
    assert client.claim("w-1") is None


def test_claim_none_on_non_dict_payload():
    client = _stub_client(lambda m, p, b: (200, ["x"]))
    assert client.claim("w-1") is None


def test_claim_none_on_other_status():
    client = _stub_client(lambda m, p, b: (400, {}))
    assert client.claim("w-1") is None


def test_claim_none_on_error():
    client = _stub_client(error=service.ControllerError("down"))
    assert client.claim("w-1") is None


def test_start_ok_on_200():
    client = _stub_client(lambda m, p, b: (200, {}))
    assert client.start("d-1") is None


def test_start_stale_on_404_and_409():
    for status in (404, 409):
        client = _stub_client(lambda m, p, b, s=status: (s, {}))
        with pytest.raises(service.StaleDispatch):
            client.start("d-1")


def test_start_stale_on_other_status():
    client = _stub_client(lambda m, p, b: (500, {}))
    with pytest.raises(service.StaleDispatch):
        client.start("d-1")


def test_start_stale_on_error():
    client = _stub_client(error=service.ControllerError("down"))
    with pytest.raises(service.StaleDispatch):
        client.start("d-1")


def test_heartbeat_returns_payload_or_empty():
    client = _stub_client(lambda m, p, b: (200, {"cancel": []}))
    assert client.heartbeat("w-1", []) == {"cancel": []}
    client2 = _stub_client(lambda m, p, b: (200, None))
    assert client2.heartbeat("w-1", []) == {}


def test_heartbeat_raises_on_non_200():
    client = _stub_client(lambda m, p, b: (503, {}))
    with pytest.raises(service.ControllerError):
        client.heartbeat("w-1", [])


def test_deliver_accepted_shapes():
    for body in ({"status": "ACCEPTED_FOR_VERIFY"}, {"status": "ACK_DUPLICATE"}, {"other": 1}):
        client = _stub_client(lambda m, p, b, body=body: (200, body))
        assert client.deliver({"dispatch_id": "d-1"}) == "accepted"


def test_deliver_stale_on_404_409():
    for status in (404, 409):
        client = _stub_client(lambda m, p, b, s=status: (s, {}))
        assert client.deliver({"dispatch_id": "d-1"}) == "stale"


def test_deliver_raises_on_other_status():
    client = _stub_client(lambda m, p, b: (400, {}))
    with pytest.raises(service.ControllerError):
        client.deliver({"dispatch_id": "d-1"})


def test_deliver_raises_on_error():
    client = _stub_client(error=service.ControllerError("down"))
    with pytest.raises(service.ControllerError):
        client.deliver({"dispatch_id": "d-1"})


# -- resolve_spec --------------------------------------------------------------

def _valid_claim(**overrides):
    claim = {
        "task_id": "task-1",
        "dispatch_id": "d-1",
        "attempt": 1,
        "ttl_s": 10,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "eff-key_1:2.3",
                 "timeout_s": 5},
    }
    claim.update(overrides)
    return claim


def test_resolve_spec_valid_maps_fields(tmp_path):
    artifacts_root = str(tmp_path / "artifacts")
    home = str(tmp_path)
    spec = service.resolve_spec(_valid_claim(), "worker-1", artifacts_root, 2.0, home=home)
    assert spec.task_id == "task-1"
    assert spec.dispatch_id == "d-1"
    assert spec.result_id == "r-d-1"
    assert spec.adapter == "synthetic"
    assert spec.effect_key == "eff-key_1:2.3"
    assert spec.artifact_dir == artifacts_root + "/d-1"
    assert spec.argv[1].endswith("adapter_runner.py")
    assert spec.timeout_s == 5.0
    assert spec.lease_ttl_s == 10.0


def test_resolve_spec_heartbeat_takes_minimum(tmp_path):
    claim = _valid_claim(heartbeat_s=1.0)
    spec = service.resolve_spec(claim, "worker-1", str(tmp_path / "a"), 2.0, home=str(tmp_path))
    assert spec.heartbeat_s == 1.0


def test_resolve_spec_rejects_non_dict_claim():
    with pytest.raises(SpecError):
        service.resolve_spec(["x"], "w", "a", 2.0)


def test_resolve_spec_rejects_missing_ids():
    for key in ("task_id", "dispatch_id"):
        claim = _valid_claim()
        del claim[key]
        with pytest.raises(SpecError):
            service.resolve_spec(claim, "w", "a", 2.0)


def test_resolve_spec_rejects_bad_attempt():
    for attempt in (0, True, "1", None):
        with pytest.raises(SpecError):
            service.resolve_spec(_valid_claim(attempt=attempt), "w", "a", 2.0)


def test_resolve_spec_rejects_bad_ttl():
    for ttl in (0, "10", None):
        with pytest.raises(SpecError):
            service.resolve_spec(_valid_claim(ttl_s=ttl), "w", "a", 2.0)


def test_resolve_spec_rejects_claim_with_argv():
    claim = _valid_claim()
    claim["spec"] = dict(claim["spec"], argv=["evil"])
    with pytest.raises(SpecError):
        service.resolve_spec(claim, "w", "a", 2.0)


def test_resolve_spec_rejects_unknown_adapter():
    claim = _valid_claim()
    claim["spec"] = {"adapter": "nope", "params": {}, "effect_key": "k1"}
    with pytest.raises(SpecError):
        service.resolve_spec(claim, "w", "a", 2.0)


def test_resolve_spec_rejects_bad_effect_key():
    for key in ("has space!", "", None, 123, "x" * 201):
        claim = _valid_claim()
        claim["spec"] = {"adapter": "synthetic", "params": {}, "effect_key": key}
        with pytest.raises(SpecError):
            service.resolve_spec(claim, "w", "a", 2.0)


def test_resolve_spec_rejects_timeout_out_of_bounds():
    # Note: falsy values (0/None) fall back to DEFAULT_TIMEOUT_S via `or`,
    # so only truthy out-of-range values are rejected.
    for timeout in (-1, 99999, "fast"):
        claim = _valid_claim()
        claim["spec"] = dict(claim["spec"], timeout_s=timeout)
        with pytest.raises(SpecError):
            service.resolve_spec(claim, "w", "a", 2.0)


def test_resolve_spec_falsy_timeout_falls_back_to_default(tmp_path):
    from courier_worker.host import DEFAULT_TIMEOUT_S
    claim = _valid_claim()
    claim["spec"] = dict(claim["spec"], timeout_s=0)
    spec = service.resolve_spec(claim, "w", str(tmp_path / "a"), 2.0, home=str(tmp_path))
    assert spec.timeout_s == float(DEFAULT_TIMEOUT_S)


def test_resolve_spec_rejects_overlong_dispatch_id(tmp_path):
    claim = _valid_claim(dispatch_id="d" * 199)
    with pytest.raises(SpecError):
        service.resolve_spec(claim, "w", str(tmp_path / "a"), 2.0, home=str(tmp_path))


# -- _artifact_prefix ----------------------------------------------------------

def test_artifact_prefix_inside_home(tmp_path):
    home = str(tmp_path)
    artifact_dir = str(tmp_path / "artifacts" / "d-1")
    assert service._artifact_prefix(artifact_dir, home) == "artifacts/d-1/"


def test_artifact_prefix_empty_without_home(tmp_path):
    assert service._artifact_prefix(str(tmp_path / "artifacts" / "d-1"), None) == ""
    assert service._artifact_prefix(str(tmp_path / "artifacts" / "d-1"), "") == ""


def test_artifact_prefix_empty_outside_home(tmp_path):
    assert service._artifact_prefix("/tmp", str(tmp_path)) == ""


# -- build_result_payload ------------------------------------------------------

def test_payload_success_without_adapter_has_no_failure_keys():
    result = _result(outcome=Outcome.COMPLETED,
                     artifacts=(ArtifactRef("out.txt", "a" * 64),))
    payload = service.build_result_payload(result)
    assert payload["outcome"] == "success"
    assert payload["artifacts"] == [{"path": "out.txt", "sha256": "a" * 64}]
    assert "retryable" not in payload
    assert "reason" not in payload


def test_payload_non_success_reports_worker_outcome():
    result = _result(outcome=Outcome.CRASH)
    payload = service.build_result_payload(result)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert "worker outcome" in payload["reason"]


def test_payload_timeout_is_retryable():
    result = _result(outcome=Outcome.TIMEOUT)
    payload = service.build_result_payload(result)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True


def test_payload_adapter_success_without_report_is_failure():
    result = _result(outcome=Outcome.COMPLETED)
    spec = _spec(adapter="synthetic", params={})
    result = ExecutionResult(spec=spec, outcome=Outcome.COMPLETED, artifacts=())
    payload = service.build_result_payload(result, None)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert "structured result" in payload["reason"]


def test_payload_adapter_failure_report_passes_through():
    spec = _spec(adapter="synthetic", params={})
    result = ExecutionResult(spec=spec, outcome=Outcome.COMPLETED, artifacts=())
    report = {"outcome": "failure", "retryable": True, "reason": "bad evidence"}
    payload = service.build_result_payload(result, report)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True
    assert payload["reason"] == "bad evidence"


def test_payload_adapter_failure_report_defaults_reason():
    spec = _spec(adapter="synthetic", params={})
    result = ExecutionResult(spec=spec, outcome=Outcome.COMPLETED, artifacts=())
    payload = service.build_result_payload(result, {"outcome": "failure"})
    assert payload["outcome"] == "failure"
    assert payload["reason"] == "adapter reported failure"


def test_payload_adapter_success_report_stays_success():
    spec = _spec(adapter="synthetic", params={})
    result = ExecutionResult(spec=spec, outcome=Outcome.COMPLETED, artifacts=())
    payload = service.build_result_payload(result, {"outcome": "success"})
    assert payload["outcome"] == "success"
    assert "retryable" not in payload


def test_payload_reason_truncated_to_500():
    spec = _spec(adapter="synthetic", params={})
    result = ExecutionResult(spec=spec, outcome=Outcome.COMPLETED, artifacts=())
    payload = service.build_result_payload(result, {"outcome": "failure", "reason": "x" * 600})
    assert len(payload["reason"]) == 500


def test_payload_artifact_prefix_applied(tmp_path):
    home = str(tmp_path)
    artifact_dir = str(tmp_path / "artifacts" / "d-1")
    spec = _spec(artifact_dir=artifact_dir)
    result = ExecutionResult(spec=spec, outcome=Outcome.COMPLETED,
                             artifacts=(ArtifactRef("out.txt", "b" * 64),))
    payload = service.build_result_payload(result, home=home)
    assert payload["artifacts"][0]["path"] == "artifacts/d-1/out.txt"


def test_build_spec_failure_payload_shape():
    payload = service.build_spec_failure_payload("d-1", "r-d-1", "spec-invalid: nope")
    assert payload == {"dispatch_id": "d-1", "result_id": "r-d-1", "artifacts": [],
                       "outcome": "failure", "retryable": False, "reason": "spec-invalid: nope"}


# -- CancelWatcher dispatch ----------------------------------------------------

def test_watcher_dispatch_sets_cancel_on_match():
    watcher = service.CancelWatcher("http://127.0.0.1:9", FAKE_TOKEN, "task-1")
    assert watcher.cancelled() is False
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "task-1"})])
    assert watcher.cancelled() is True


def test_watcher_dispatch_ignores_other_task():
    watcher = service.CancelWatcher("http://127.0.0.1:9", FAKE_TOKEN, "task-1")
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "task-2"})])
    assert watcher.cancelled() is False


def test_watcher_dispatch_ignores_non_cancel_type():
    watcher = service.CancelWatcher("http://127.0.0.1:9", FAKE_TOKEN, "task-1")
    watcher._dispatch_event([json.dumps({"type": "SOMETHING_ELSE", "task_id": "task-1"})])
    assert watcher.cancelled() is False


def test_watcher_dispatch_ignores_bad_json_and_shapes():
    watcher = service.CancelWatcher("http://127.0.0.1:9", FAKE_TOKEN, "task-1")
    watcher._dispatch_event(["not json"])
    watcher._dispatch_event([json.dumps(["list"])])
    watcher._dispatch_event([])
    assert watcher.cancelled() is False


def test_watcher_dispatch_handles_wrapped_and_event_type_keys():
    watcher = service.CancelWatcher("http://127.0.0.1:9", FAKE_TOKEN, "task-1")
    watcher._dispatch_event([json.dumps({"payload": {"type": "TASK_CANCELLED", "task_id": "task-1"}})])
    assert watcher.cancelled() is True
    watcher2 = service.CancelWatcher("http://127.0.0.1:9", FAKE_TOKEN, "task-1")
    watcher2._dispatch_event([json.dumps({"event_type": "TASK_CANCELLED", "task_id": "task-1"})])
    assert watcher2.cancelled() is True


def test_result_payload_is_plain_json():
    # The controller accepts the payload unchanged: it must be plain JSON.
    result = _result(outcome=Outcome.COMPLETED,
                     artifacts=(ArtifactRef("out.txt", "c" * 64),))
    payload = service.build_result_payload(result)
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
