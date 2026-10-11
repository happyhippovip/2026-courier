"""Offline contract pins for courier_worker.service (P9 test hardening).

Tests only; no behavior change. Everything here runs without network,
threads, subprocesses, or a controller: HTTP is replaced by small fakes,
and only pure helpers plus constructor/argv validation are exercised.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

from courier_worker import service as S
from courier_worker.host import ArtifactRef, ExecutionResult, ExecutionSpec, Outcome, SpecError
from courier_worker.service import (
    CANCEL_TYPES,
    FLUSH_TIMEOUT_S,
    REQUEST_TIMEOUT_S,
    SSE_POLL_S,
    SSE_RECONNECTS,
    STARTUP_HEALTH_ATTEMPTS,
    STARTUP_HEALTH_SLEEP_S,
    CancelWatcher,
    ControllerClient,
    ControllerError,
    ControllerUnreachable,
    StaleDispatch,
    _artifact_prefix,
    build_result_payload,
    build_spec_failure_payload,
    main,
    resolve_spec,
)

BASE_URL = "http://controller.invalid"
TOKEN = "tok-1"


# -- error taxonomy -----------------------------------------------------------

def test_controller_error_is_a_runtime_error():
    exc = ControllerError("boom")
    assert isinstance(exc, RuntimeError)
    assert str(exc) == "boom"


def test_error_subclasses_are_catchable_as_controller_error():
    for cls in (ControllerUnreachable, StaleDispatch):
        assert issubclass(cls, ControllerError)
        with pytest.raises(ControllerError):
            raise cls("x")


def test_unreachable_and_stale_are_distinct():
    assert not isinstance(ControllerUnreachable("x"), StaleDispatch)
    assert not isinstance(StaleDispatch("x"), ControllerUnreachable)


# -- tuning constants ----------------------------------------------------------

def test_timeout_and_reconnect_constants():
    assert S.REQUEST_TIMEOUT_S == 10.0
    assert S.STARTUP_HEALTH_ATTEMPTS == 5
    assert S.STARTUP_HEALTH_SLEEP_S == 1.0
    assert S.FLUSH_TIMEOUT_S == 3.0
    assert S.SSE_RECONNECTS == 3
    assert S.SSE_POLL_S == 0.25
    assert REQUEST_TIMEOUT_S > 0 and FLUSH_TIMEOUT_S > 0 and SSE_POLL_S > 0
    assert STARTUP_HEALTH_ATTEMPTS >= 1 and SSE_RECONNECTS >= 0


def test_cancel_types_exact_membership():
    assert CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
    assert "TASK_CREATED" not in CANCEL_TYPES


# -- client construction (no I/O) ----------------------------------------------

def test_client_accepts_http_and_https():
    assert ControllerClient("http://controller.invalid", TOKEN).base_url == BASE_URL
    assert ControllerClient("https://controller.invalid:8443/a", TOKEN).base_url == \
        "https://controller.invalid:8443/a"


def test_client_strips_trailing_slashes_and_stores_token_timeout():
    client = ControllerClient(BASE_URL + "///", TOKEN, timeout_s=2.5)
    assert client.base_url == BASE_URL
    assert client.token == TOKEN
    assert client.timeout_s == 2.5
    assert ControllerClient(BASE_URL, TOKEN).timeout_s == REQUEST_TIMEOUT_S


@pytest.mark.parametrize("bad", ["ftp://controller.invalid/x", "http://", "", "notaurl"])
def test_client_rejects_bad_controller_url(bad):
    with pytest.raises(ControllerError):
        ControllerClient(bad, TOKEN)


# -- _call wire discipline (fake connection: still no network) ------------------

class _FakeResp:
    def __init__(self, status, raw):
        self.status = status
        self._raw = raw

    def read(self):
        return self._raw


class _FakeConn:
    def __init__(self, status=200, raw=b"{}", fail=None):
        self.status = status
        self.raw = raw
        self.fail = fail
        self.seen = None
        self.closed = False

    def request(self, method, path, body=None, headers=None):
        if self.fail is not None:
            raise self.fail
        self.seen = {"method": method, "path": path, "body": body, "headers": headers}

    def getresponse(self):
        return _FakeResp(self.status, self.raw)

    def close(self):
        self.closed = True


def _stubbed_client(status=200, raw=b"{}", fail=None):
    client = ControllerClient(BASE_URL, TOKEN)
    fake = _FakeConn(status=status, raw=raw, fail=fail)
    client._conn = lambda: fake
    return client, fake


def test_call_prefixes_v1_and_sends_token_header():
    client, fake = _stubbed_client(raw=b'{"ok": true}')
    status, payload = client._call("POST", "/claim", {"worker_id": "w1"})
    assert (status, payload) == (200, {"ok": True})
    assert fake.seen["method"] == "POST"
    assert fake.seen["path"] == "/v1/claim"
    assert fake.seen["body"] == json.dumps({"worker_id": "w1"})
    assert fake.seen["headers"]["X-Courier-Token"] == TOKEN
    assert fake.seen["headers"]["Accept"] == "application/json"
    assert fake.seen["headers"]["Content-Type"] == "application/json"
    assert fake.closed


def test_call_without_body_sends_no_content_type():
    client, fake = _stubbed_client()
    client._call("GET", "/health")
    assert fake.seen["path"] == "/v1/health"
    assert fake.seen["body"] is None
    assert "Content-Type" not in fake.seen["headers"]
    assert fake.seen["headers"]["X-Courier-Token"] == TOKEN


def test_call_server_error_and_transport_error_raise_and_close():
    client, fake = _stubbed_client(status=503, raw=b"{}")
    with pytest.raises(ControllerError):
        client._call("GET", "/health")
    assert fake.closed
    client, fake = _stubbed_client(fail=OSError("down"))
    with pytest.raises(ControllerError):
        client._call("GET", "/health")
    assert fake.closed


@pytest.mark.parametrize("raw", [b"{oops", b"", b"null"])
def test_call_tolerates_empty_or_non_object_bodies(raw):
    client, fake = _stubbed_client(raw=raw)
    status, payload = client._call("GET", "/health")
    assert status == 200
    assert payload is None
    assert fake.closed


# -- resolve_spec (fail closed, still no I/O) ------------------------------------

def _claim(task_id="t1", dispatch_id="d1", attempt=1, ttl_s=30, spec=None, heartbeat_s=5):
    if spec is None:
        spec = {"adapter": "synthetic", "params": {}, "effect_key": "ek-1"}
    return {"task_id": task_id, "dispatch_id": dispatch_id, "attempt": attempt,
            "ttl_s": ttl_s, "spec": spec, "heartbeat_s": heartbeat_s}


def test_resolve_spec_maps_a_valid_claim(tmp_path):
    home = str(tmp_path)
    artifacts_root = str(tmp_path / "artifacts")
    spec = resolve_spec(_claim(), "w1", artifacts_root, 2.0, home=home)
    assert isinstance(spec, ExecutionSpec)
    assert (spec.task_id, spec.attempt, spec.dispatch_id, spec.worker_id) == ("t1", 1, "d1", "w1")
    assert spec.result_id == "r-d1"
    assert spec.adapter == "synthetic" and spec.params == {} and spec.effect_key == "ek-1"
    assert spec.artifact_dir == os.path.join(artifacts_root, "d1")
    assert spec.timeout_s == 300.0 and isinstance(spec.timeout_s, float)
    assert spec.lease_ttl_s == 30.0
    assert spec.heartbeat_s == 2.0
    assert spec.argv[0] == sys.executable
    assert spec.argv[1].endswith("adapter_runner.py")
    assert spec.argv[2] == os.path.join(home, "run", "requests", "d1.json")


@pytest.mark.parametrize("claim_hb, expected", [(1.0, 1.0), (9.0, 2.0), (0, 2.0), ("fast", 2.0)])
def test_resolve_spec_takes_the_smaller_positive_heartbeat(tmp_path, claim_hb, expected):
    spec = resolve_spec(_claim(heartbeat_s=claim_hb), "w1", str(tmp_path), 2.0, home=str(tmp_path))
    assert spec.heartbeat_s == expected


def test_resolve_spec_honours_a_valid_timeout(tmp_path):
    spec_body = {"adapter": "synthetic", "params": {}, "effect_key": "ek-1", "timeout_s": 10}
    spec = resolve_spec(_claim(spec=spec_body), "w1", str(tmp_path), 2.0, home=str(tmp_path))
    assert spec.timeout_s == 10.0


@pytest.mark.parametrize("timeout_s", [0, None])
def test_resolve_spec_treats_a_falsy_timeout_as_default(tmp_path, timeout_s):
    spec_body = {"adapter": "synthetic", "params": {}, "effect_key": "ek-1", "timeout_s": timeout_s}
    spec = resolve_spec(_claim(spec=spec_body), "w1", str(tmp_path), 2.0, home=str(tmp_path))
    assert spec.timeout_s == 300.0


@pytest.mark.parametrize("timeout_s", [-1, 3601, "10", [30]])
def test_resolve_spec_rejects_an_out_of_bounds_timeout(tmp_path, timeout_s):
    spec_body = {"adapter": "synthetic", "params": {}, "effect_key": "ek-1", "timeout_s": timeout_s}
    with pytest.raises(SpecError):
        resolve_spec(_claim(spec=spec_body), "w1", str(tmp_path), 2.0, home=str(tmp_path))


@pytest.mark.parametrize("attempt", [True, 0, -3, "1", 1.5, None])
def test_resolve_spec_rejects_a_bad_attempt(tmp_path, attempt):
    with pytest.raises(SpecError):
        resolve_spec(_claim(attempt=attempt), "w1", str(tmp_path), 2.0, home=str(tmp_path))


@pytest.mark.parametrize("ttl_s", [0, -5, "30", None, {}])
def test_resolve_spec_rejects_a_bad_ttl(tmp_path, ttl_s):
    with pytest.raises(SpecError):
        resolve_spec(_claim(ttl_s=ttl_s), "w1", str(tmp_path), 2.0, home=str(tmp_path))


def test_resolve_spec_requires_ids_and_a_spec_object(tmp_path):
    base = _claim()
    for key in ("task_id", "dispatch_id", "attempt", "ttl_s", "spec"):
        body = dict(base)
        del body[key]
        with pytest.raises(SpecError):
            resolve_spec(body, "w1", str(tmp_path), 2.0, home=str(tmp_path))
    with pytest.raises(SpecError):
        resolve_spec("not-a-claim", "w1", str(tmp_path), 2.0, home=str(tmp_path))
    with pytest.raises(SpecError):
        resolve_spec(_claim(task_id="", dispatch_id=""), "w1", str(tmp_path), 2.0,
                     home=str(tmp_path))


@pytest.mark.parametrize("spec", [
    {"adapter": "unknown", "params": {}, "effect_key": "ek-1"},
    {"adapter": "synthetic", "params": [], "effect_key": "ek-1"},
    {"adapter": "synthetic", "params": {}, "effect_key": "ek-1", "argv": ["evil"]},
    {"adapter": "synthetic", "params": {}},
    {"adapter": "synthetic", "params": {"sleep_s": -1}, "effect_key": "ek-1"},
])
def test_resolve_spec_rejects_a_bad_adapter_spec(tmp_path, spec):
    with pytest.raises(SpecError):
        resolve_spec(_claim(spec=spec), "w1", str(tmp_path), 2.0, home=str(tmp_path))


def test_resolve_spec_bounds_the_result_id(tmp_path):
    resolve_spec(_claim(dispatch_id="d" * 198), "w1", str(tmp_path), 2.0, home=str(tmp_path))
    with pytest.raises(SpecError):
        resolve_spec(_claim(dispatch_id="d" * 199), "w1", str(tmp_path), 2.0,
                     home=str(tmp_path))


# -- artifact prefix containment ---------------------------------------------------

def test_artifact_prefix_inside_home(tmp_path):
    home = str(tmp_path)
    assert _artifact_prefix(os.path.join(home, "artifacts", "d1"), home) == "artifacts/d1/"
    assert _artifact_prefix(os.path.join(home, "..", tmp_path.name, "artifacts", "d1"), home) == \
        "artifacts/d1/"


def test_artifact_prefix_empty_without_or_at_home(tmp_path):
    home = str(tmp_path)
    assert _artifact_prefix(os.path.join(home, "artifacts", "d1"), None) == ""
    assert _artifact_prefix(os.path.join(home, "artifacts", "d1"), "") == ""
    assert _artifact_prefix(home, home) == ""


def test_artifact_prefix_empty_outside_home(tmp_path):
    elsewhere = str(tmp_path.parent / (tmp_path.name + "-other"))
    assert _artifact_prefix(elsewhere, str(tmp_path)) == ""


# -- result payloads -----------------------------------------------------------------

def _plain_spec(tmp_path, dispatch="d1", adapter=None):
    return ExecutionSpec(task_id="t1", attempt=1, dispatch_id=dispatch, worker_id="w1",
                         result_id="r-" + dispatch, argv=("run",), timeout_s=30.0,
                         lease_ttl_s=30.0, artifact_dir=str(tmp_path / "artifacts" / dispatch),
                         heartbeat_s=2.0, adapter=adapter,
                         params={} if adapter else None, effect_key="ek-1" if adapter else None)


def test_plain_success_has_the_golden_shape(tmp_path):
    result = ExecutionResult(spec=_plain_spec(tmp_path),
                             outcome=Outcome.COMPLETED,
                             artifacts=(ArtifactRef("out.txt", "a" * 64),))
    payload = build_result_payload(result, home=str(tmp_path))
    assert payload == {"dispatch_id": "d1", "result_id": "r-d1",
                       "artifacts": [{"path": "artifacts/d1/out.txt", "sha256": "a" * 64}],
                       "outcome": "success"}


@pytest.mark.parametrize("outcome, retryable", [(Outcome.TIMEOUT, True), (Outcome.CRASH, False),
                                                (Outcome.CANCELLED, False), (Outcome.LEASE_LOST, True)])
def test_non_success_reports_worker_outcome(tmp_path, outcome, retryable):
    result = ExecutionResult(spec=_plain_spec(tmp_path), outcome=outcome)
    payload = build_result_payload(result, home=str(tmp_path))
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is retryable
    assert payload["reason"] == f"worker outcome: {outcome}"


def test_bridged_run_without_a_report_is_a_non_retryable_failure(tmp_path):
    result = ExecutionResult(spec=_plain_spec(tmp_path, adapter="synthetic"),
                             outcome=Outcome.COMPLETED)
    payload = build_result_payload(result, None, home=str(tmp_path))
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert payload["reason"] == "adapter runner produced no structured result"


def test_bridged_failure_report_passes_through_retryability(tmp_path):
    result = ExecutionResult(spec=_plain_spec(tmp_path, adapter="synthetic"),
                             outcome=Outcome.COMPLETED)
    payload = build_result_payload(result, {"outcome": "failure", "retryable": True,
                                            "reason": "boom"}, home=str(tmp_path))
    assert (payload["outcome"], payload["retryable"], payload["reason"]) == \
        ("failure", True, "boom")
    payload = build_result_payload(result, {"outcome": "failure"}, home=str(tmp_path))
    assert (payload["retryable"], payload["reason"]) == (False, "adapter reported failure")


def test_bridged_success_report_keeps_the_golden_shape(tmp_path):
    result = ExecutionResult(spec=_plain_spec(tmp_path, adapter="synthetic"),
                             outcome=Outcome.COMPLETED)
    payload = build_result_payload(result, {"outcome": "success"}, home=str(tmp_path))
    assert payload["outcome"] == "success"
    assert "retryable" not in payload and "reason" not in payload


def test_adapter_reason_is_bounded(tmp_path):
    result = ExecutionResult(spec=_plain_spec(tmp_path, adapter="synthetic"),
                             outcome=Outcome.COMPLETED)
    payload = build_result_payload(result, {"outcome": "failure", "reason": "x" * 600},
                                   home=str(tmp_path))
    assert len(payload["reason"]) == 500


def test_artifacts_are_unprefixed_without_a_home(tmp_path):
    result = ExecutionResult(spec=_plain_spec(tmp_path),
                             outcome=Outcome.COMPLETED,
                             artifacts=(ArtifactRef("sub/out.txt", "b" * 64),))
    payload = build_result_payload(result, home=None)
    assert payload["artifacts"] == [{"path": "sub/out.txt", "sha256": "b" * 64}]


def test_spec_failure_payload_shape():
    assert build_spec_failure_payload("d1", "r-d1", "why") == \
        {"dispatch_id": "d1", "result_id": "r-d1", "artifacts": [],
         "outcome": "failure", "retryable": False, "reason": "why"}


# -- cancel watcher dispatch (pure event parsing) ---------------------------------------

def _watcher(task_id="t1"):
    return CancelWatcher(BASE_URL, TOKEN, task_id)


def test_watcher_starts_uncancelled():
    watcher = _watcher()
    assert watcher.task_id == "t1" and watcher.token == TOKEN
    assert watcher.timeout_s == REQUEST_TIMEOUT_S
    assert watcher.degraded is False
    assert watcher.cancelled() is False


@pytest.mark.parametrize("lines", [[], ["not json"], ["[1, 2]"], ['"str"'], ["42"]])
def test_watcher_ignores_empty_and_non_object_events(lines):
    watcher = _watcher()
    watcher._dispatch_event(lines)
    assert watcher.cancelled() is False


@pytest.mark.parametrize("event_type", ["TASK_CANCEL_REQUESTED", "TASK_CANCELLED"])
def test_watcher_fires_on_cancel_for_its_task(event_type):
    watcher = _watcher()
    watcher._dispatch_event([json.dumps({"type": event_type, "task_id": "t1"})])
    assert watcher.cancelled() is True


@pytest.mark.parametrize("body", [
    {"type": "TASK_CANCELLED", "task_id": "other"},
    {"type": "TASK_CREATED", "task_id": "t1"},
    {"type": "RESULT_READY", "task_id": "t1"},
])
def test_watcher_ignores_other_tasks_and_types(body):
    watcher = _watcher()
    watcher._dispatch_event([json.dumps(body)])
    assert watcher.cancelled() is False


def test_watcher_reads_nested_and_alternate_keys():
    watcher = _watcher()
    watcher._dispatch_event([json.dumps({"payload": {"type": "TASK_CANCELLED",
                                                    "task_id": "t1"}})])
    assert watcher.cancelled() is True
    watcher = _watcher()
    watcher._dispatch_event([json.dumps({"event_type": "TASK_CANCEL_REQUESTED",
                                         "task_id": "t1"})])
    assert watcher.cancelled() is True


def test_watcher_joins_multi_line_data():
    watcher = _watcher()
    watcher._dispatch_event(['{', '"type": "TASK_CANCELLED",', '"task_id": "t1"', '}'])
    assert watcher.cancelled() is True


# -- worker entry-point guards (argv validation only) ------------------------------------

@pytest.mark.parametrize("argv", [
    [],
    ["--controller", BASE_URL, "--max-tasks", "2"],
    ["--controller", BASE_URL, "--heartbeat", "0.01"],
    ["--controller", BASE_URL, "--heartbeat", "60"],
])
def test_main_rejects_bad_argv_without_running(argv):
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2
