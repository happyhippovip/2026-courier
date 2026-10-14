"""Tests for courier_worker.service (Item P9 test hardening).

Covers:
- ControllerError and error subclasses
- ControllerClient URL parsing and HTTP method wrappers
- resolve_spec claim validation and spec mapping
- _artifact_prefix relative path calculation
- build_result_payload and build_spec_failure_payload
- CancelWatcher event parsing and state transition
- CLI argument parsing and validation
"""

from __future__ import annotations

import os
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

from courier_worker.host import (
    DEFAULT_TIMEOUT_S,
    ExecutionResult,
    ExecutionSpec,
    Outcome,
    SpecError,
)
from courier_worker.service import (
    CANCEL_TYPES,
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


# -----------------------------------------------------------------------------
# ControllerClient URL Parsing & Error Tests
# -----------------------------------------------------------------------------

def test_controller_client_url_validation():
    # Valid HTTP and HTTPS URLs
    c1 = ControllerClient("http://127.0.0.1:8080", "tok")
    assert c1.base_url == "http://127.0.0.1:8080"

    c2 = ControllerClient("https://example.com/api/", "tok")
    assert c2.base_url == "https://example.com/api"

    # Invalid scheme or missing hostname
    with pytest.raises(ControllerError, match="bad controller url"):
        ControllerClient("ftp://127.0.0.1:8080", "tok")

    with pytest.raises(ControllerError, match="bad controller url"):
        ControllerClient("http://", "tok")

    with pytest.raises(ControllerError, match="bad controller url"):
        ControllerClient("just-a-string", "tok")


def test_controller_client_call_methods():
    client = ControllerClient("http://127.0.0.1:8080", "secret-token")

    # health()
    with patch.object(client, "_call", return_value=(200, {"mode": "WRITER"})):
        assert client.health() is True
    with patch.object(client, "_call", side_effect=ControllerError("conn error")):
        assert client.health() is False

    # claim()
    with patch.object(client, "_call", return_value=(204, None)):
        assert client.claim("worker-1") is None
    with patch.object(client, "_call", return_value=(200, {"task_id": "t1"})):
        assert client.claim("worker-1") == {"task_id": "t1"}
    with patch.object(client, "_call", side_effect=ControllerError("err")):
        assert client.claim("worker-1") is None

    # start()
    with patch.object(client, "_call", return_value=(200, {})):
        client.start("disp-1")  # No raise

    with patch.object(client, "_call", return_value=(404, {})):
        with pytest.raises(StaleDispatch):
            client.start("disp-1")

    with patch.object(client, "_call", return_value=(409, {})):
        with pytest.raises(StaleDispatch):
            client.start("disp-1")

    # heartbeat()
    with patch.object(client, "_call", return_value=(200, {"stop": ["disp-old"]})):
        hb = client.heartbeat("w1", ["disp-1"])
        assert hb == {"stop": ["disp-old"]}

    with patch.object(client, "_call", return_value=(500, {})):
        with pytest.raises(ControllerError):
            client.heartbeat("w1", ["disp-1"])

    # deliver()
    with patch.object(client, "_call", return_value=(200, {"status": "ACCEPTED_FOR_VERIFY"})):
        assert client.deliver({"dispatch_id": "d1"}) == "accepted"

    with patch.object(client, "_call", return_value=(404, {})):
        assert client.deliver({"dispatch_id": "d1"}) == "stale"

    with patch.object(client, "_call", return_value=(409, {})):
        assert client.deliver({"dispatch_id": "d1"}) == "stale"


# -----------------------------------------------------------------------------
# resolve_spec Tests
# -----------------------------------------------------------------------------

def test_resolve_spec_valid():
    claim = {
        "task_id": "task-100",
        "dispatch_id": "disp-200",
        "attempt": 1,
        "ttl_s": 30.0,
        "spec": {
            "adapter": "synthetic",
            "params": {"duration_ms": 10},
            "effect_class": "idempotent",
            "effect_key": "ek-200",
            "timeout_s": 15.0,
        },
    }
    spec = resolve_spec(claim, worker_id="worker-test", artifacts_root="/tmp/art", heartbeat_s=2.0)
    assert spec.task_id == "task-100"
    assert spec.dispatch_id == "disp-200"
    assert spec.attempt == 1
    assert spec.timeout_s == 15.0
    assert spec.lease_ttl_s == 30.0
    assert spec.worker_id == "worker-test"
    assert spec.adapter == "synthetic"
    assert spec.effect_key == "ek-200"
    assert spec.result_id == "r-disp-200"


def test_resolve_spec_invalid_claims():
    # Not a dict
    with pytest.raises(SpecError, match="claim is not an object"):
        resolve_spec("not a dict", "w1", "/tmp", 2.0)  # type: ignore

    # Missing task_id
    with pytest.raises(SpecError, match="no task_id"):
        resolve_spec({"dispatch_id": "d1", "attempt": 1, "ttl_s": 10}, "w1", "/tmp", 2.0)

    # Missing dispatch_id
    with pytest.raises(SpecError, match="no dispatch_id"):
        resolve_spec({"task_id": "t1", "attempt": 1, "ttl_s": 10}, "w1", "/tmp", 2.0)

    # Invalid attempt (bool, 0, or negative)
    with pytest.raises(SpecError, match="no valid attempt"):
        resolve_spec({"task_id": "t1", "dispatch_id": "d1", "attempt": True, "ttl_s": 10}, "w1", "/tmp", 2.0)

    with pytest.raises(SpecError, match="no valid attempt"):
        resolve_spec({"task_id": "t1", "dispatch_id": "d1", "attempt": 0, "ttl_s": 10}, "w1", "/tmp", 2.0)

    # Invalid ttl_s
    with pytest.raises(SpecError, match="no valid ttl_s"):
        resolve_spec({"task_id": "t1", "dispatch_id": "d1", "attempt": 1, "ttl_s": 0}, "w1", "/tmp", 2.0)

    # Oversized dispatch_id
    with pytest.raises(SpecError, match="room for a result_id"):
        huge_disp = "d" * 205
        claim = {
            "task_id": "t1",
            "dispatch_id": huge_disp,
            "attempt": 1,
            "ttl_s": 10,
            "spec": {
                "adapter": "synthetic",
                "params": {"duration_ms": 10},
                "effect_class": "idempotent",
                "effect_key": "ek-huge",
            },
        }
        resolve_spec(claim, "w1", "/tmp", 2.0)


# -----------------------------------------------------------------------------
# Artifact Prefix and Payload Builders
# -----------------------------------------------------------------------------

def test_artifact_prefix():
    home = os.path.abspath("/tmp/courier_home")
    inside = os.path.join(home, "artifacts", "disp-1")
    assert _artifact_prefix(inside, home) == "artifacts/disp-1/"

    outside = os.path.abspath("/var/log/disp-1")
    assert _artifact_prefix(outside, home) == ""
    assert _artifact_prefix(inside, None) == ""


def test_build_spec_failure_payload():
    payload = build_spec_failure_payload("disp-1", "res-1", "bad spec format")
    assert payload["dispatch_id"] == "disp-1"
    assert payload["result_id"] == "res-1"
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert payload["reason"] == "bad spec format"


def test_build_result_payload_success_and_failure():
    spec = ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="disp-1",
        worker_id="w1",
        result_id="res-1",
        argv=["dummy"],
        timeout_s=10.0,
        lease_ttl_s=30.0,
        artifact_dir="/tmp/art/disp-1",
        heartbeat_s=2.0,
        adapter="synthetic",
    )
    # 1. Success with missing report in bridged adapter run -> treated as failure
    res_success = ExecutionResult(
        spec=spec,
        outcome=Outcome.COMPLETED,
        returncode=0,
        was_signal=False,
        artifacts=(),
        crash_report_path=None,
        duration_s=1.0,
        wakes=0,
        stale=False,
    )
    p1 = build_result_payload(res_success, report=None)
    assert p1["outcome"] == "failure"
    assert p1["retryable"] is False
    assert "no structured result" in p1["reason"]

    # 2. Success with valid report
    report_success = {"outcome": "success"}
    p2 = build_result_payload(res_success, report=report_success)
    assert p2["outcome"] == "success"
    assert "retryable" not in p2  # success payload omits retryable

    # 3. Execution failure
    res_failed = ExecutionResult(
        spec=spec,
        outcome=Outcome.CRASH,
        returncode=1,
        was_signal=False,
        artifacts=(),
        crash_report_path=None,
        duration_s=0.5,
        wakes=0,
        stale=False,
    )
    p3 = build_result_payload(res_failed, report=None)
    assert p3["outcome"] == "failure"
    assert "worker outcome" in p3["reason"]


# -----------------------------------------------------------------------------
# CancelWatcher Event Dispatch Tests
# -----------------------------------------------------------------------------

def test_cancel_watcher_dispatch():
    watcher = CancelWatcher("http://127.0.0.1:8080", "tok", "task-cancel-target")
    assert not watcher.cancelled()

    # Unrelated task cancellation event
    watcher._dispatch_event(['{"type": "TASK_CANCEL_REQUESTED", "task_id": "other-task"}'])
    assert not watcher.cancelled()

    # Unrelated event type for our task
    watcher._dispatch_event(['{"type": "TASK_STARTED", "task_id": "task-cancel-target"}'])
    assert not watcher.cancelled()

    # Valid task cancellation event
    watcher._dispatch_event(['{"type": "TASK_CANCEL_REQUESTED", "task_id": "task-cancel-target"}'])
    assert watcher.cancelled()


# -----------------------------------------------------------------------------
# CLI Argument Parsing Tests
# -----------------------------------------------------------------------------

def test_main_cli_arguments():
    # Missing --controller argument
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2

    # --max-tasks != 1
    with pytest.raises(SystemExit) as exc:
        main(["--controller", "http://127.0.0.1:8080", "--max-tasks", "2"])
    assert exc.value.code == 2

    # --heartbeat out of range
    with pytest.raises(SystemExit) as exc:
        main(["--controller", "http://127.0.0.1:8080", "--heartbeat", "0.1"])
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        main(["--controller", "http://127.0.0.1:8080", "--heartbeat", "50.0"])
    assert exc.value.code == 2


# -----------------------------------------------------------------------------
# WorkerLoop Lifecycle Tests
# -----------------------------------------------------------------------------

def test_worker_loop_flush_outbox(tmp_path: Path):
    from courier_worker.host import outbox_write
    from courier_worker.service import WorkerLoop

    home = str(tmp_path)
    client = MagicMock()
    loop = WorkerLoop(home, "http://127.0.0.1:8080", "w1", 2.0, client_factory=lambda: client)

    # Empty outbox
    assert loop.flush_outbox() == 0

    # Write outbox item and deliver successfully
    outbox_write(home, {"dispatch_id": "disp-1", "outcome": "success"})
    client.deliver.return_value = "accepted"
    assert loop.flush_outbox() == 0

    # Write outbox item with delivery failure
    outbox_write(home, {"dispatch_id": "disp-2", "outcome": "success"})
    client.deliver.side_effect = ControllerError("unreachable")
    assert loop.flush_outbox() == 1


def test_worker_loop_iterate_idle_and_spec_rejected(tmp_path: Path):
    from courier_worker.service import WorkerLoop

    home = str(tmp_path)
    client = MagicMock()
    loop = WorkerLoop(home, "http://127.0.0.1:8080", "w1", 2.0, client_factory=lambda: client)
    stop = threading.Event()

    # 1. Claim is None -> "idle"
    client.claim.return_value = None
    assert loop.iterate(stop) == "idle"

    # 2. Claim has invalid spec -> "spec-rejected"
    client.claim.return_value = {"dispatch_id": "d1", "spec": "not-a-dict"}
    client.deliver.return_value = "accepted"
    assert loop.iterate(stop) == "spec-rejected"


def test_worker_loop_send_heartbeat_signals_cancellation(tmp_path: Path):
    from courier_worker.service import WorkerLoop

    home = str(tmp_path)
    client = MagicMock()
    loop = WorkerLoop(home, "http://127.0.0.1:8080", "w1", 2.0, client_factory=lambda: client)
    watcher = CancelWatcher("http://127.0.0.1:8080", "tok", "task-1")
    loop._watchers["disp-1"] = watcher

    spec = MagicMock()
    spec.dispatch_id = "disp-1"

    # Heartbeat returns cancel
    client.heartbeat.return_value = {"cancel": ["disp-1"], "stop": []}
    assert loop._send_heartbeat(client, spec) is True
    assert watcher.cancelled() is True
