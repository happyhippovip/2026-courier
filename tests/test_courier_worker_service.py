"""Dedicated tests for courier_worker.service (Lane L4, Pool Item P9)."""

import http.client
import io
import json
import os
import socket
import sys
import threading
import time
from unittest.mock import MagicMock, call, patch

import pytest

from courier_worker import adapter_bridge as A
from courier_worker import service as S
from courier_worker.host import (
    ArtifactRef,
    ExecutionResult,
    ExecutionSpec,
    HostBusy,
    Outcome,
    ResourcePaused,
    SpecError,
)


# -- 1. Constants and Exception Hierarchy ---------------------------------------


def test_service_constants():
    assert "TASK_CANCEL_REQUESTED" in S.CANCEL_TYPES
    assert "TASK_CANCELLED" in S.CANCEL_TYPES
    assert S.CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
    assert S.REQUEST_TIMEOUT_S == 10.0
    assert S.STARTUP_HEALTH_ATTEMPTS == 5
    assert S.STARTUP_HEALTH_SLEEP_S == 1.0
    assert S.FLUSH_TIMEOUT_S == 3.0
    assert S.SSE_RECONNECTS == 3
    assert S.SSE_POLL_S == 0.25


def test_exceptions_hierarchy():
    assert issubclass(S.ControllerError, RuntimeError)
    assert issubclass(S.ControllerUnreachable, S.ControllerError)
    assert issubclass(S.StaleDispatch, S.ControllerError)

    err = S.ControllerError("network timeout")
    assert str(err) == "network timeout"
    unreachable = S.ControllerUnreachable("no server")
    assert isinstance(unreachable, S.ControllerError)
    stale = S.StaleDispatch("cancelled task")
    assert isinstance(stale, S.ControllerError)


# -- 2. ControllerClient --------------------------------------------------------


def test_controller_client_url_validation():
    with pytest.raises(S.ControllerError, match="bad controller url"):
        S.ControllerClient("ftp://127.0.0.1:8080", "tok")

    with pytest.raises(S.ControllerError, match="bad controller url"):
        S.ControllerClient("http://", "tok")

    with pytest.raises(S.ControllerError, match="bad controller url"):
        S.ControllerClient("not-a-url", "tok")

    client = S.ControllerClient("http://127.0.0.1:8080/", "tok", timeout_s=5.0)
    assert client.base_url == "http://127.0.0.1:8080"
    assert client.token == "tok"
    assert client.timeout_s == 5.0


def test_controller_client_conn_creation():
    client_http = S.ControllerClient("http://127.0.0.1:9090", "tok")
    conn_http = client_http._conn()
    assert isinstance(conn_http, http.client.HTTPConnection)
    assert conn_http.host == "127.0.0.1"
    assert conn_http.port == 9090
    assert conn_http.timeout == S.REQUEST_TIMEOUT_S

    client_https = S.ControllerClient("https://controller.internal", "tok", timeout_s=8.0)
    conn_https = client_https._conn()
    assert isinstance(conn_https, http.client.HTTPSConnection)
    assert conn_https.host == "controller.internal"
    assert conn_https.port == 443
    assert conn_https.timeout == 8.0


def test_controller_client_call_success_with_headers_and_body():
    client = S.ControllerClient("http://127.0.0.1:8080", "my-token")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"status": "ok", "count": 1}).encode("utf-8")

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch.object(client, "_conn", return_value=mock_conn):
        status, payload = client._call("POST", "/claim", {"worker_id": "w1"})

    assert status == 200
    assert payload == {"status": "ok", "count": 1}
    mock_conn.request.assert_called_once_with(
        "POST",
        "/v1/claim",
        body=json.dumps({"worker_id": "w1"}),
        headers={
            "X-Courier-Token": "my-token",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    mock_conn.close.assert_called_once()


def test_controller_client_call_server_error_5xx():
    client = S.ControllerClient("http://127.0.0.1:8080", "tok")
    mock_resp = MagicMock()
    mock_resp.status = 503
    mock_resp.read.return_value = b"Service Unavailable"

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch.object(client, "_conn", return_value=mock_conn):
        with pytest.raises(S.ControllerError, match="status 503"):
            client._call("GET", "/health")

    mock_conn.close.assert_called_once()


def test_controller_client_call_network_exception_mapping():
    client = S.ControllerClient("http://127.0.0.1:8080", "tok")
    mock_conn = MagicMock()
    mock_conn.request.side_effect = socket.timeout("timed out")

    with patch.object(client, "_conn", return_value=mock_conn):
        with pytest.raises(S.ControllerError, match="timed out"):
            client._call("GET", "/health")

    mock_conn.close.assert_called_once()


def test_controller_client_call_non_json_payload_returns_none():
    client = S.ControllerClient("http://127.0.0.1:8080", "tok")
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b"<html>Not JSON</html>"

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch.object(client, "_conn", return_value=mock_conn):
        status, payload = client._call("GET", "/status")

    assert status == 200
    assert payload is None


def test_controller_client_health():
    client = S.ControllerClient("http://127.0.0.1:8080", "tok")

    with patch.object(client, "_call", return_value=(200, {"healthy": True})):
        assert client.health() is True

    with patch.object(client, "_call", return_value=(404, None)):
        assert client.health() is False

    with patch.object(client, "_call", side_effect=S.ControllerError("network down")):
        assert client.health() is False


def test_controller_client_claim():
    client = S.ControllerClient("http://127.0.0.1:8080", "tok")

    # 200 with dict
    claim_dict = {"task_id": "t1", "dispatch_id": "d1"}
    with patch.object(client, "_call", return_value=(200, claim_dict)):
        assert client.claim("w1") == claim_dict

    # 204 No Content
    with patch.object(client, "_call", return_value=(204, None)):
        assert client.claim("w1") is None

    # 200 with non-dict
    with patch.object(client, "_call", return_value=(200, "string-not-dict")):
        assert client.claim("w1") is None

    # ControllerError
    with patch.object(client, "_call", side_effect=S.ControllerError("timeout")):
        assert client.claim("w1") is None


def test_controller_client_start():
    client = S.ControllerClient("http://127.0.0.1:8080", "tok")

    # 200 OK
    with patch.object(client, "_call", return_value=(200, None)):
        client.start("d1")  # does not raise

    # 404 / 409 -> StaleDispatch
    with patch.object(client, "_call", return_value=(404, None)):
        with pytest.raises(S.StaleDispatch, match="rejects dispatch d1: 404"):
            client.start("d1")

    with patch.object(client, "_call", return_value=(409, None)):
        with pytest.raises(S.StaleDispatch, match="rejects dispatch d1: 409"):
            client.start("d1")

    # Non-200 -> StaleDispatch
    with patch.object(client, "_call", return_value=(400, None)):
        with pytest.raises(S.StaleDispatch, match="status 400"):
            client.start("d1")

    # ControllerError -> StaleDispatch
    with patch.object(client, "_call", side_effect=S.ControllerError("connection reset")):
        with pytest.raises(S.StaleDispatch, match="connection reset"):
            client.start("d1")


def test_controller_client_heartbeat():
    client = S.ControllerClient("http://127.0.0.1:8080", "tok")

    # 200 OK
    with patch.object(client, "_call", return_value=(200, {"cancel": ["d1"]})):
        res = client.heartbeat("w1", ["d1"])
        assert res == {"cancel": ["d1"]}

    # 200 OK with None payload defaults to empty dict
    with patch.object(client, "_call", return_value=(200, None)):
        assert client.heartbeat("w1", ["d1"]) == {}

    # Non-200 raises ControllerError
    with patch.object(client, "_call", return_value=(400, None)):
        with pytest.raises(S.ControllerError, match="heartbeat: status 400"):
            client.heartbeat("w1", ["d1"])


def test_controller_client_deliver():
    client = S.ControllerClient("http://127.0.0.1:8080", "tok")

    # 200 with ACCEPTED_FOR_VERIFY
    with patch.object(client, "_call", return_value=(200, {"status": "ACCEPTED_FOR_VERIFY"})):
        assert client.deliver({"dispatch_id": "d1"}) == "accepted"

    # 200 with ACK_DUPLICATE
    with patch.object(client, "_call", return_value=(200, {"status": "ACK_DUPLICATE"})):
        assert client.deliver({"dispatch_id": "d1"}) == "accepted"

    # 200 plain
    with patch.object(client, "_call", return_value=(200, {})):
        assert client.deliver({"dispatch_id": "d1"}) == "accepted"

    # 404 / 409 -> "stale"
    with patch.object(client, "_call", return_value=(404, None)):
        assert client.deliver({"dispatch_id": "d1"}) == "stale"

    with patch.object(client, "_call", return_value=(409, None)):
        assert client.deliver({"dispatch_id": "d1"}) == "stale"

    # non-200 -> raises ControllerError
    with patch.object(client, "_call", return_value=(400, None)):
        with pytest.raises(S.ControllerError, match="result: status 400"):
            client.deliver({"dispatch_id": "d1"})


# -- 3. Artifact Prefix and Spec Resolution -------------------------------------


def test_artifact_prefix(tmp_path):
    home = tmp_path / "home"
    home.mkdir()

    # None home
    assert S._artifact_prefix(str(home / "artifacts" / "d1"), None) == ""

    # Inside home
    art_dir = home / "artifacts" / "d1"
    art_dir.mkdir(parents=True)
    assert S._artifact_prefix(str(art_dir), str(home)) == "artifacts/d1/"

    # Subdir inside home
    sub_dir = home / "custom" / "path"
    assert S._artifact_prefix(str(sub_dir), str(home)) == "custom/path/"

    # Exactly home (curdir)
    assert S._artifact_prefix(str(home), str(home)) == ""

    # Outside home
    outside = tmp_path / "other" / "artifacts"
    assert S._artifact_prefix(str(outside), str(home)) == ""


def test_resolve_spec_valid(tmp_path):
    claim = {
        "task_id": "task-42",
        "dispatch_id": "dsp-101",
        "attempt": 2,
        "ttl_s": 120.0,
        "heartbeat_s": 1.5,
        "spec": {
            "adapter": "synthetic",
            "params": {"sleep_s": 0.05},
            "effect_key": "eff-101",
            "timeout_s": 60.0,
        },
    }
    spec = S.resolve_spec(
        claim,
        worker_id="worker-test",
        artifacts_root=str(tmp_path / "artifacts"),
        heartbeat_s=2.0,
        home=str(tmp_path),
    )
    assert spec.task_id == "task-42"
    assert spec.dispatch_id == "dsp-101"
    assert spec.attempt == 2
    assert spec.worker_id == "worker-test"
    assert spec.result_id == "r-dsp-101"
    assert spec.timeout_s == 60.0
    assert spec.lease_ttl_s == 120.0
    assert spec.heartbeat_s == 1.5  # min(2.0, 1.5)
    assert spec.adapter == "synthetic"
    assert spec.params == {"sleep_s": 0.05}
    assert spec.effect_key == "eff-101"
    assert spec.artifact_dir == str(tmp_path / "artifacts" / "dsp-101")


def test_resolve_spec_rejects_non_dict_claim():
    with pytest.raises(SpecError, match="claim is not an object"):
        S.resolve_spec("not-a-dict", "w1", "/tmp/art", 2.0)


def test_resolve_spec_rejects_missing_task_or_dispatch():
    base = {
        "attempt": 1,
        "ttl_s": 30.0,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "k"},
    }
    with pytest.raises(SpecError, match="claim carries no task_id"):
        S.resolve_spec({**base, "dispatch_id": "d1"}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim carries no task_id"):
        S.resolve_spec({**base, "task_id": "", "dispatch_id": "d1"}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim carries no dispatch_id"):
        S.resolve_spec({**base, "task_id": "t1"}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim carries no dispatch_id"):
        S.resolve_spec({**base, "task_id": "t1", "dispatch_id": ""}, "w1", "/tmp/art", 2.0)


def test_resolve_spec_rejects_invalid_attempt():
    base = {
        "task_id": "t1",
        "dispatch_id": "d1",
        "ttl_s": 30.0,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "k"},
    }
    with pytest.raises(SpecError, match="claim carries no valid attempt"):
        S.resolve_spec({**base, "attempt": True}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim carries no valid attempt"):
        S.resolve_spec({**base, "attempt": 0}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim carries no valid attempt"):
        S.resolve_spec({**base, "attempt": "1"}, "w1", "/tmp/art", 2.0)


def test_resolve_spec_rejects_invalid_ttl():
    base = {
        "task_id": "t1",
        "dispatch_id": "d1",
        "attempt": 1,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "k"},
    }
    with pytest.raises(SpecError, match="claim carries no valid ttl_s"):
        S.resolve_spec({**base, "ttl_s": 0}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim carries no valid ttl_s"):
        S.resolve_spec({**base, "ttl_s": -5.0}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim carries no valid ttl_s"):
        S.resolve_spec({**base, "ttl_s": "30"}, "w1", "/tmp/art", 2.0)


def test_resolve_spec_timeout_bounds():
    base = {
        "task_id": "t1",
        "dispatch_id": "d1",
        "attempt": 1,
        "ttl_s": 30.0,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "k"},
    }
    # Out of bounds timeouts
    with pytest.raises(SpecError, match="claim spec timeout_s is out of bounds"):
        S.resolve_spec({**base, "spec": {**base["spec"], "timeout_s": -1.0}}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim spec timeout_s is out of bounds"):
        S.resolve_spec({**base, "spec": {**base["spec"], "timeout_s": S.MAX_TIMEOUT_S + 1}}, "w1", "/tmp/art", 2.0)

    with pytest.raises(SpecError, match="claim spec timeout_s is out of bounds"):
        S.resolve_spec({**base, "spec": {**base["spec"], "timeout_s": "slow"}}, "w1", "/tmp/art", 2.0)


def test_resolve_spec_dispatch_id_length_bound():
    base = {
        "task_id": "t1",
        "dispatch_id": "d" * 199,  # len("r-" + "d"*199) == 201 > 200
        "attempt": 1,
        "ttl_s": 30.0,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "k"},
    }
    with pytest.raises(SpecError, match="leaves no room for a result_id within 200 chars"):
        S.resolve_spec(base, "w1", "/tmp/art", 2.0)


# -- 4. Result Payload Builders ------------------------------------------------


def test_build_spec_failure_payload():
    payload = S.build_spec_failure_payload("dsp-9", "r-dsp-9", "bad spec format")
    assert payload == {
        "dispatch_id": "dsp-9",
        "result_id": "r-dsp-9",
        "artifacts": [],
        "outcome": "failure",
        "retryable": False,
        "reason": "bad spec format",
    }


def test_build_result_payload_success_without_adapter():
    spec = ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=("echo", "hi"),
        timeout_s=30.0,
        lease_ttl_s=30.0,
        artifact_dir="/home/user/artifacts/d1",
        heartbeat_s=1.0,
        adapter=None,
    )
    result = ExecutionResult(
        spec=spec,
        outcome=Outcome.COMPLETED,
        returncode=0,
        artifacts=[ArtifactRef("report.txt", "abc123sha")],
    )
    payload = S.build_result_payload(result, report=None, home="/home/user")
    assert payload == {
        "dispatch_id": "d1",
        "result_id": "r-d1",
        "artifacts": [{"path": "artifacts/d1/report.txt", "sha256": "abc123sha"}],
        "outcome": "success",
    }
    assert "retryable" not in payload
    assert "reason" not in payload


def test_build_result_payload_worker_outcome_not_success():
    spec = ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=("echo", "hi"),
        timeout_s=30.0,
        lease_ttl_s=30.0,
        artifact_dir="/home/user/artifacts/d1",
        heartbeat_s=1.0,
        adapter="synthetic",
    )
    # Timeout outcome is retryable
    result_timeout = ExecutionResult(
        spec=spec,
        outcome=Outcome.TIMEOUT,
        returncode=-9,
        artifacts=[],
    )
    payload_timeout = S.build_result_payload(result_timeout, report=None, home="/home/user")
    assert payload_timeout["outcome"] == "failure"
    assert payload_timeout["retryable"] is True
    assert payload_timeout["reason"] == "worker outcome: timeout"

    # Crash outcome is non-retryable
    result_crash = ExecutionResult(
        spec=spec,
        outcome=Outcome.CRASH,
        returncode=139,
        artifacts=[],
    )
    payload_crash = S.build_result_payload(result_crash, report=None, home="/home/user")
    assert payload_crash["outcome"] == "failure"
    assert payload_crash["retryable"] is False
    assert payload_crash["reason"] == "worker outcome: crash"


def test_build_result_payload_bridged_missing_report():
    spec = ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=("echo", "hi"),
        timeout_s=30.0,
        lease_ttl_s=30.0,
        artifact_dir="/home/user/artifacts/d1",
        heartbeat_s=1.0,
        adapter="synthetic",
    )
    result = ExecutionResult(
        spec=spec,
        outcome=Outcome.COMPLETED,
        returncode=0,
        artifacts=[],
    )
    payload = S.build_result_payload(result, report=None, home="/home/user")
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert payload["reason"] == "adapter runner produced no structured result"


def test_build_result_payload_bridged_failure_report():
    spec = ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=("echo", "hi"),
        timeout_s=30.0,
        lease_ttl_s=30.0,
        artifact_dir="/home/user/artifacts/d1",
        heartbeat_s=1.0,
        adapter="synthetic",
    )
    result = ExecutionResult(
        spec=spec,
        outcome=Outcome.COMPLETED,
        returncode=0,
        artifacts=[],
    )
    long_reason = "fault occurred: " + ("x" * 600)
    report = {
        "outcome": "failure",
        "retryable": True,
        "reason": long_reason,
    }
    payload = S.build_result_payload(result, report=report, home="/home/user")
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True
    assert len(payload["reason"]) == 500
    assert payload["reason"] == long_reason[:500]


def test_build_result_payload_bridged_success_report():
    spec = ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=("echo", "hi"),
        timeout_s=30.0,
        lease_ttl_s=30.0,
        artifact_dir="/home/user/artifacts/d1",
        heartbeat_s=1.0,
        adapter="synthetic",
    )
    result = ExecutionResult(
        spec=spec,
        outcome=Outcome.COMPLETED,
        returncode=0,
        artifacts=[ArtifactRef("data/output.json", "sha-out")],
    )
    report = {"outcome": "success"}
    payload = S.build_result_payload(result, report=report, home="/home/user")
    assert payload["outcome"] == "success"
    assert payload["artifacts"] == [{"path": "artifacts/d1/data/output.json", "sha256": "sha-out"}]
    assert "retryable" not in payload
    assert "reason" not in payload


# -- 5. CancelWatcher -----------------------------------------------------------


def test_cancel_watcher_dispatch_event():
    watcher = S.CancelWatcher("http://127.0.0.1:8080", "tok", "target-task")
    assert not watcher.cancelled()

    # Empty data
    watcher._dispatch_event([])
    assert not watcher.cancelled()

    # Invalid JSON
    watcher._dispatch_event(["not-json"])
    assert not watcher.cancelled()

    # Non-dict JSON
    watcher._dispatch_event(["[1, 2, 3]"])
    assert not watcher.cancelled()

    # Different event type
    watcher._dispatch_event([json.dumps({"type": "TASK_STARTED", "task_id": "target-task"})])
    assert not watcher.cancelled()

    # Different task_id
    watcher._dispatch_event([json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "other-task"})])
    assert not watcher.cancelled()

    # Nested payload cancellation for our task
    watcher._dispatch_event([json.dumps({"payload": {"type": "TASK_CANCEL_REQUESTED", "task_id": "target-task"}})])
    assert watcher.cancelled()


def test_cancel_watcher_stop():
    watcher = S.CancelWatcher("http://127.0.0.1:8080", "tok", "target-task")
    watcher._stop.set()
    assert not watcher._thread
    watcher.stop()  # idempotent when thread is None


def test_cancel_watcher_follow_clean_eof(monkeypatch):
    watcher = S.CancelWatcher("http://127.0.0.1:8080", "tok", "target-task")
    # _subscribe returns cleanly (EOF)
    monkeypatch.setattr(watcher, "_subscribe", lambda: None)
    watcher._follow()
    assert not watcher.degraded


def test_cancel_watcher_follow_reconnects_exceeded(monkeypatch):
    watcher = S.CancelWatcher("http://127.0.0.1:8080", "tok", "target-task")
    monkeypatch.setattr(S, "SSE_RECONNECTS", 2)
    calls = 0

    def fail_subscribe():
        nonlocal calls
        calls += 1
        raise OSError("connection refused")

    monkeypatch.setattr(watcher, "_subscribe", fail_subscribe)
    watcher._follow()
    assert watcher.degraded is True
    assert calls == 3  # initial + 2 reconnects


# -- 6. WorkerLoop --------------------------------------------------------------


def test_worker_loop_artifacts_root():
    loop = S.WorkerLoop("/var/courier/home", "http://127.0.0.1:8080", "w1", 1.0)
    assert loop.artifacts_root() == os.path.join("/var/courier/home", "artifacts")


def test_worker_loop_default_client_reads_token(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    token_file = run_dir / "controller.token"

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0)

    # Missing token file
    with pytest.raises(S.ControllerUnreachable, match="no controller token"):
        loop._default_client()

    # Empty token file
    token_file.write_text("   \n")
    with pytest.raises(S.ControllerUnreachable, match="token file is empty"):
        loop._default_client()

    # Valid token file
    token_file.write_text("secret-jwt-token-123\n")
    client = loop._default_client()
    assert client.token == "secret-jwt-token-123"
    assert client.base_url == "http://127.0.0.1:8080"


def test_worker_loop_flush_outbox(tmp_path):
    p1 = {"dispatch_id": "d1", "outcome": "success"}
    p2 = {"dispatch_id": "d2", "outcome": "failure"}
    S.outbox_write(str(tmp_path), p1)
    S.outbox_write(str(tmp_path), p2)

    mock_client = MagicMock()

    def fake_deliver(payload):
        if payload["dispatch_id"] == "d1":
            return "accepted"
        raise S.ControllerError("controller temporary error")

    mock_client.deliver.side_effect = fake_deliver

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0,
                        client_factory=lambda: mock_client)

    remaining = loop.flush_outbox()
    assert remaining == 1
    assert not (tmp_path / "outbox" / "d1.json").exists()
    assert (tmp_path / "outbox" / "d2.json").exists()


def test_worker_loop_iterate_idle_when_flush_fails(tmp_path):
    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0)
    with patch.object(loop, "flush_outbox", side_effect=S.ControllerError("network down")):
        assert loop.iterate(threading.Event()) == "idle"


def test_worker_loop_iterate_idle_when_no_claim(tmp_path):
    mock_client = MagicMock()
    mock_client.claim.return_value = None

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0,
                        client_factory=lambda: mock_client)
    with patch.object(loop, "flush_outbox", return_value=0):
        assert loop.iterate(threading.Event()) == "idle"


def test_worker_loop_iterate_spec_rejected(tmp_path):
    mock_client = MagicMock()
    mock_client.claim.return_value = {"task_id": "t1"}  # missing dispatch_id and spec

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0,
                        client_factory=lambda: mock_client)

    with patch.object(loop, "flush_outbox", return_value=0), \
         patch.object(loop, "_deliver_payload") as mock_deliver:
        assert loop.iterate(threading.Event()) == "spec-rejected"
        mock_deliver.assert_called_once()
        payload = mock_deliver.call_args[0][0]
        assert payload["outcome"] == "failure"
        assert payload["retryable"] is False
        assert "spec-invalid" in payload["reason"]


def test_worker_loop_iterate_stale_dispatch_at_start(tmp_path):
    mock_client = MagicMock()
    claim = {
        "task_id": "t1",
        "dispatch_id": "dsp-stale",
        "attempt": 1,
        "ttl_s": 30.0,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "k1"},
    }
    mock_client.claim.return_value = claim
    mock_client.start.side_effect = S.StaleDispatch("cancelled before start")

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0,
                        client_factory=lambda: mock_client)

    with patch.object(loop, "flush_outbox", return_value=0), \
         patch("courier_worker.adapter_bridge.cleanup") as mock_cleanup:
        assert loop.iterate(threading.Event()) == "stale"
        mock_cleanup.assert_called_once_with(str(tmp_path), "dsp-stale")


def test_worker_loop_iterate_host_shutdown_abandoned(tmp_path):
    mock_client = MagicMock()
    claim = {
        "task_id": "t1",
        "dispatch_id": "dsp-abandon",
        "attempt": 1,
        "ttl_s": 30.0,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "k1"},
    }
    mock_client.claim.return_value = claim

    mock_engine = MagicMock()
    spec = S.resolve_spec(claim, "w1", str(tmp_path / "artifacts"), 1.0, home=str(tmp_path))
    result = ExecutionResult(spec=spec, outcome=Outcome.CANCELLED, returncode=-15)
    mock_engine.run_once.return_value = result

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0,
                        engine=mock_engine, client_factory=lambda: mock_client)

    with patch.object(loop, "flush_outbox", return_value=0), \
         patch.object(loop, "_deliver_payload") as mock_deliver, \
         patch("courier_worker.adapter_bridge.cleanup") as mock_cleanup:
        assert loop.iterate(threading.Event()) == "abandoned"
        mock_deliver.assert_not_called()  # abandoned does not deliver
        mock_cleanup.assert_called_once_with(str(tmp_path), "dsp-abandon")


def test_worker_loop_iterate_task_cancelled_delivers_and_beats(tmp_path):
    mock_client = MagicMock()
    claim = {
        "task_id": "t1",
        "dispatch_id": "dsp-cancel",
        "attempt": 1,
        "ttl_s": 30.0,
        "spec": {"adapter": "synthetic", "params": {}, "effect_key": "k1"},
    }
    mock_client.claim.return_value = claim

    mock_engine = MagicMock()
    spec = S.resolve_spec(claim, "w1", str(tmp_path / "artifacts"), 1.0, home=str(tmp_path))
    result = ExecutionResult(spec=spec, outcome=Outcome.CANCELLED, returncode=-15)

    def fake_run_once(_spec, on_heartbeat=None, is_cancelled=None):
        # Trigger watcher cancellation simulating task cancel event from controller
        watcher = loop._watchers.get(spec.dispatch_id)
        if watcher:
            watcher._cancelled.set()
        return result

    mock_engine.run_once.side_effect = fake_run_once

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0,
                        engine=mock_engine, client_factory=lambda: mock_client)

    with patch.object(loop, "flush_outbox", return_value=0), \
         patch.object(loop, "_deliver_payload") as mock_deliver, \
         patch("courier_worker.adapter_bridge.cleanup") as mock_cleanup:
        assert loop.iterate(threading.Event()) == "delivered"
        mock_deliver.assert_called_once()
        mock_cleanup.assert_called_once_with(str(tmp_path), "dsp-cancel")
        mock_client.heartbeat.assert_called_once_with("w1", [])


def test_worker_loop_send_heartbeat_detects_cancel():
    mock_client = MagicMock()
    mock_client.heartbeat.return_value = {"cancel": ["d1"], "stop": []}

    loop = S.WorkerLoop("/home", "http://127.0.0.1:8080", "w1", 1.0)
    fake_watcher = MagicMock()
    loop._watchers["d1"] = fake_watcher

    spec = MagicMock()
    spec.dispatch_id = "d1"

    loop._send_heartbeat(mock_client, spec)
    fake_watcher._cancelled.set.assert_called_once()


def test_worker_loop_deliver_payload_handles_controller_error(tmp_path):
    mock_client = MagicMock()
    mock_client.deliver.side_effect = S.ControllerError("network timeout")

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 1.0,
                        client_factory=lambda: mock_client)
    loop._client = mock_client

    payload = {"dispatch_id": "d-fail", "outcome": "failure"}
    loop._deliver_payload(payload)

    # Item must remain in outbox
    outbox_file = tmp_path / "outbox" / "d-fail.json"
    assert outbox_file.exists()


# -- 7. CLI Entrypoint (main) ---------------------------------------------------


def test_main_cli_argument_validation():
    # --max-tasks != 1 must exit 2
    with pytest.raises(SystemExit) as exc1:
        S.main(["--controller", "http://127.0.0.1:8080", "--max-tasks", "2"])
    assert exc1.value.code == 2

    # --heartbeat < 0.2 must exit 2
    with pytest.raises(SystemExit) as exc2:
        S.main(["--controller", "http://127.0.0.1:8080", "--heartbeat", "0.1"])
    assert exc2.value.code == 2

    # --heartbeat > 30.0 must exit 2
    with pytest.raises(SystemExit) as exc3:
        S.main(["--controller", "http://127.0.0.1:8080", "--heartbeat", "35.0"])
    assert exc3.value.code == 2


# -- 8. WorkerLoop.run Lifecycle and Error Handling -----------------------------


def test_worker_loop_run_unhealthy_controller_raises(tmp_path):
    write_token_file = tmp_path / "run" / "controller.token"
    write_token_file.parent.mkdir(parents=True, exist_ok=True)
    write_token_file.write_text("valid-tok")

    mock_client = MagicMock()
    mock_client.health.return_value = False

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 0.05,
                        client_factory=lambda: mock_client)

    with patch.object(S, "STARTUP_HEALTH_SLEEP_S", 0.01), \
         patch.object(S, "STARTUP_HEALTH_ATTEMPTS", 2), \
         patch("courier_worker.service.acquire_home_lock", return_value=99), \
         patch("courier_worker.service.release_home_lock") as mock_release, \
         patch("courier_worker.service.run_orphan_gate"):
        with pytest.raises(S.ControllerUnreachable, match="unhealthy after 2 attempts"):
            loop.run()
        mock_release.assert_called_once_with(99)


def test_worker_loop_run_stop_during_startup(tmp_path):
    write_token_file = tmp_path / "run" / "controller.token"
    write_token_file.parent.mkdir(parents=True, exist_ok=True)
    write_token_file.write_text("valid-tok")

    stop = threading.Event()
    stop.set()  # Already stopped

    mock_client = MagicMock()
    mock_client.health.return_value = False

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 0.05,
                        client_factory=lambda: mock_client)

    with patch("courier_worker.service.acquire_home_lock", return_value=42), \
         patch("courier_worker.service.release_home_lock") as mock_release, \
         patch("courier_worker.service.run_orphan_gate"):
        code = loop.run(stop)
        assert code == 0
        mock_release.assert_called_once_with(42)


def test_worker_loop_run_handles_host_busy(tmp_path):
    mock_client = MagicMock()
    mock_client.health.return_value = True

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 0.05)

    with patch.object(loop, "_default_client", return_value=mock_client), \
         patch.object(loop, "iterate", side_effect=HostBusy("already running")), \
         patch("courier_worker.service.acquire_home_lock", return_value=12), \
         patch("courier_worker.service.release_home_lock") as mock_release, \
         patch("courier_worker.service.run_orphan_gate"):
        assert loop.run() == 0
        mock_release.assert_called_once_with(12)


def test_worker_loop_run_handles_resource_paused(tmp_path, capsys):
    mock_client = MagicMock()
    mock_client.health.return_value = True

    stop = threading.Event()
    calls = 0

    def fake_iterate(_stop):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ResourcePaused("thermal pressure")
        stop.set()
        return "idle"

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 0.01)

    with patch.object(loop, "_default_client", return_value=mock_client), \
         patch.object(loop, "iterate", side_effect=fake_iterate), \
         patch("courier_worker.service.acquire_home_lock", return_value=15), \
         patch("courier_worker.service.release_home_lock") as mock_release, \
         patch("courier_worker.service.run_orphan_gate"):
        assert loop.run(stop) == 0
        mock_release.assert_called_once_with(15)

    captured = capsys.readouterr()
    assert "paused due to resource pressure: RESOURCE_PAUSE: thermal pressure" in captured.err


def test_worker_loop_run_clean_shutdown_flushes_outbox(tmp_path):
    mock_client = MagicMock()
    mock_client.health.return_value = True

    stop = threading.Event()

    def fake_iterate(_stop):
        stop.set()
        return "idle"

    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:8080", "w1", 0.01)

    # When flush_outbox succeeds with remaining=0 -> exit 0
    with patch.object(loop, "_default_client", return_value=mock_client), \
         patch.object(loop, "iterate", side_effect=fake_iterate), \
         patch.object(loop, "flush_outbox", return_value=0), \
         patch("courier_worker.service.acquire_home_lock", return_value=20), \
         patch("courier_worker.service.release_home_lock") as mock_release, \
         patch("courier_worker.service.run_orphan_gate"):
        assert loop.run(stop) == 0
        mock_release.assert_called_once_with(20)

    # When flush_outbox leaves items remaining > 0 -> exit 1
    stop.clear()
    with patch.object(loop, "_default_client", return_value=mock_client), \
         patch.object(loop, "iterate", side_effect=fake_iterate), \
         patch.object(loop, "flush_outbox", return_value=2), \
         patch("courier_worker.service.acquire_home_lock", return_value=21), \
         patch("courier_worker.service.release_home_lock") as mock_release, \
         patch("courier_worker.service.run_orphan_gate"):
        assert loop.run(stop) == 1
        mock_release.assert_called_once_with(21)


# -- 9. CancelWatcher Stream Protocol Tests -------------------------------------


def test_cancel_watcher_subscribe_protocol_errors():
    watcher = S.CancelWatcher("http://127.0.0.1:8080", "tok", "t1", timeout_s=0.1)

    # Status not 200 raises ControllerError
    mock_sock = MagicMock()
    mock_sock.recv.side_effect = [
        b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n",
        b"",
    ]
    with patch("socket.create_connection", return_value=mock_sock):
        with pytest.raises(S.ControllerError, match="sse: status 401"):
            watcher._subscribe()
        mock_sock.close.assert_called_once()

    # Chunked stream raises ControllerError
    mock_sock_chunked = MagicMock()
    mock_sock_chunked.recv.side_effect = [
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n",
        b"",
    ]
    with patch("socket.create_connection", return_value=mock_sock_chunked):
        with pytest.raises(S.ControllerError, match="chunked stream not supported"):
            watcher._subscribe()
        mock_sock_chunked.close.assert_called_once()

    # Oversized headers raises ControllerError
    mock_sock_oversized = MagicMock()
    mock_sock_oversized.recv.return_value = b"X" * 70000
    with patch("socket.create_connection", return_value=mock_sock_oversized):
        with pytest.raises(S.ControllerError, match="oversized headers"):
            watcher._subscribe()
        mock_sock_oversized.close.assert_called_once()


def test_cancel_watcher_subscribe_valid_event_stream():
    watcher = S.CancelWatcher("http://127.0.0.1:8080", "tok", "target-task", timeout_s=1.0)

    event_payload = json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "target-task"})
    sse_response = (
        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n"
        b": keepalive\n\n"
        b"data: " + event_payload.encode("utf-8") + b"\n\n"
    )

    mock_sock = MagicMock()
    mock_sock.recv.side_effect = [sse_response, b""]

    with patch("socket.create_connection", return_value=mock_sock):
        watcher._subscribe()

    assert watcher.cancelled() is True
    mock_sock.close.assert_called_once()


def test_main_cli_handles_exceptions():
    # HostBusy -> exit 3
    with patch.object(S.WorkerLoop, "run", side_effect=HostBusy("locked")):
        assert S.main(["--controller", "http://127.0.0.1:8080"]) == 3

    # ControllerUnreachable -> exit 4
    with patch.object(S.WorkerLoop, "run", side_effect=S.ControllerUnreachable("no server")):
        assert S.main(["--controller", "http://127.0.0.1:8080"]) == 4

