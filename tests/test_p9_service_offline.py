"""P9 offline pins for courier_worker.service (tests only, no behavior change).

Covers only offline, deterministic surface: error hierarchy, constants,
ControllerClient URL validation (no connections), result-payload builders,
artifact-prefix helper, CancelWatcher event dispatch (no sockets/threads),
resolve_spec fail-closed edges, and main() argv validation (no run loop).

No network, no credentials, no processes spawned.
"""

from __future__ import annotations

import pytest

from courier_worker import service
from courier_worker.host import ArtifactRef, ExecutionResult, ExecutionSpec, Outcome
from courier_worker.service import (
    CANCEL_TYPES,
    ControllerClient,
    ControllerError,
    ControllerUnreachable,
    StaleDispatch,
    build_result_payload,
    build_spec_failure_payload,
)


def _spec(tmp_path, adapter=None, outcome_argv=None):
    artifact_dir = str(tmp_path / "artifacts" / "d1")
    return ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=tuple(outcome_argv or ["run", "x"]),
        timeout_s=5.0,
        lease_ttl_s=60.0,
        artifact_dir=artifact_dir,
        heartbeat_s=1.0,
        adapter=adapter,
        params={"sleep_s": 0} if adapter else None,
        effect_key="eff.1" if adapter else None,
    )


def _result(spec, outcome=Outcome.COMPLETED):
    return ExecutionResult(spec=spec, outcome=outcome, returncode=0)


# -- error hierarchy ---------------------------------------------------------


def test_error_hierarchy():
    assert issubclass(ControllerUnreachable, ControllerError)
    assert issubclass(StaleDispatch, ControllerError)
    assert issubclass(ControllerError, RuntimeError)


def test_constants():
    assert service.REQUEST_TIMEOUT_S == 10.0
    assert service.STARTUP_HEALTH_ATTEMPTS == 5
    assert service.FLUSH_TIMEOUT_S == 3.0
    assert service.SSE_RECONNECTS == 3
    assert service.SSE_POLL_S == 0.25
    assert CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
    assert isinstance(CANCEL_TYPES, frozenset)


# -- ControllerClient URL validation (no network) -----------------------------


def test_client_rejects_bad_scheme():
    with pytest.raises(ControllerError):
        ControllerClient("ftp://host/x", "tok")


def test_client_rejects_missing_host():
    with pytest.raises(ControllerError):
        ControllerClient("http://", "tok")
    with pytest.raises(ControllerError):
        ControllerClient("not-a-url", "tok")


def test_client_strips_trailing_slash():
    client = ControllerClient("http://127.0.0.1:9/", "tok")
    assert client.base_url == "http://127.0.0.1:9"


def test_client_stores_token_and_timeout():
    client = ControllerClient("http://127.0.0.1:9", "tok", timeout_s=2.5)
    assert client.token == "tok"
    assert client.timeout_s == 2.5


def test_client_default_timeout():
    client = ControllerClient("https://example.invalid", "tok")
    assert client.timeout_s == service.REQUEST_TIMEOUT_S


# -- payload builders ---------------------------------------------------------


def test_spec_failure_payload_shape():
    payload = build_spec_failure_payload("d1", "r-d1", "boom")
    assert payload == {
        "dispatch_id": "d1",
        "result_id": "r-d1",
        "artifacts": [],
        "outcome": "failure",
        "retryable": False,
        "reason": "boom",
    }


def test_artifact_prefix_no_home(tmp_path):
    assert service._artifact_prefix(str(tmp_path / "a"), None) == ""
    assert service._artifact_prefix(str(tmp_path / "a"), "") == ""


def test_artifact_prefix_outside_home(tmp_path):
    home = str(tmp_path / "home")
    outside = str(tmp_path / "elsewhere" / "d1")
    assert service._artifact_prefix(outside, home) == ""


def test_artifact_prefix_inside_home(tmp_path):
    home = str(tmp_path / "home")
    inner = str(tmp_path / "home" / "artifacts" / "d1")
    assert service._artifact_prefix(inner, home) == "artifacts/d1/"


def test_artifact_prefix_exact_home_is_empty(tmp_path):
    home = str(tmp_path / "home")
    assert service._artifact_prefix(home, home) == ""


def test_build_result_success_wire_shape(tmp_path):
    spec = _spec(tmp_path)
    payload = build_result_payload(_result(spec), home=None)
    assert payload["outcome"] == "success"
    assert payload["dispatch_id"] == "d1"
    assert payload["result_id"] == "r-d1"
    assert payload["artifacts"] == []
    assert "retryable" not in payload
    assert "reason" not in payload


def test_build_result_failure_carries_retryable(tmp_path):
    spec = _spec(tmp_path)
    payload = build_result_payload(_result(spec, Outcome.TIMEOUT), home=None)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True
    assert "worker outcome" in payload["reason"]


def test_build_result_crash_not_retryable(tmp_path):
    spec = _spec(tmp_path)
    payload = build_result_payload(_result(spec, Outcome.CRASH), home=None)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False


def test_build_result_bridged_missing_report_is_failure(tmp_path):
    spec = _spec(tmp_path, adapter="synthetic")
    payload = build_result_payload(_result(spec), report=None, home=None)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert "no structured result" in payload["reason"]


def test_build_result_bridged_failure_report(tmp_path):
    spec = _spec(tmp_path, adapter="synthetic")
    report = {"outcome": "failure", "retryable": True, "reason": "adapter said no"}
    payload = build_result_payload(_result(spec), report=report, home=None)
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True
    assert payload["reason"] == "adapter said no"


def test_build_result_bridged_failure_reason_truncated(tmp_path):
    spec = _spec(tmp_path, adapter="synthetic")
    report = {"outcome": "failure", "retryable": False, "reason": "x" * 600}
    payload = build_result_payload(_result(spec), report=report, home=None)
    assert len(payload["reason"]) <= 500


def test_build_result_bridged_success_report_stays_success(tmp_path):
    spec = _spec(tmp_path, adapter="synthetic")
    payload = build_result_payload(
        _result(spec), report={"outcome": "success"}, home=None
    )
    assert payload["outcome"] == "success"
    assert "retryable" not in payload


def test_build_result_artifact_prefix_applied(tmp_path):
    home = tmp_path / "home"
    artifact_dir = home / "artifacts" / "d1"
    spec = ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=["run", "x"],
        timeout_s=5.0,
        lease_ttl_s=60.0,
        artifact_dir=str(artifact_dir),
        heartbeat_s=1.0,
    )
    result = ExecutionResult(
        spec=spec,
        outcome=Outcome.COMPLETED,
        artifacts=(ArtifactRef(path="out.txt", sha256="abc"),),
    )
    payload = build_result_payload(result, home=str(home))
    assert payload["artifacts"] == [{"path": "artifacts/d1/out.txt", "sha256": "abc"}]


# -- CancelWatcher dispatch (no threads/sockets) ------------------------------


def _watcher():
    return service.CancelWatcher("http://127.0.0.1:9", "tok", "t1")


def test_cancel_dispatch_empty_noop():
    watcher = _watcher()
    watcher._dispatch_event([])
    assert not watcher.cancelled()


def test_cancel_dispatch_invalid_json_noop():
    watcher = _watcher()
    watcher._dispatch_event(["not json"])
    assert not watcher.cancelled()


def test_cancel_dispatch_non_dict_noop():
    import json

    watcher = _watcher()
    watcher._dispatch_event([json.dumps([1, 2, 3])])
    assert not watcher.cancelled()


def test_cancel_matching_sets_event():
    import json

    watcher = _watcher()
    watcher._dispatch_event(
        [json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "t1"})]
    )
    assert watcher.cancelled()


def test_cancel_wrong_task_no_set():
    import json

    watcher = _watcher()
    watcher._dispatch_event(
        [json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": "other"})]
    )
    assert not watcher.cancelled()


def test_cancel_wrong_type_no_set():
    import json

    watcher = _watcher()
    watcher._dispatch_event([json.dumps({"type": "HEARTBEAT", "task_id": "t1"})])
    assert not watcher.cancelled()


def test_cancel_payload_wrapped_inner():
    import json

    watcher = _watcher()
    watcher._dispatch_event(
        [json.dumps({"payload": {"type": "TASK_CANCELLED", "task_id": "t1"}})]
    )
    assert watcher.cancelled()


# -- resolve_spec fail-closed edges (no network) ------------------------------


def test_resolve_spec_rejects_non_dict(tmp_path):
    from courier_worker.host import SpecError

    with pytest.raises(SpecError):
        service.resolve_spec([], "w1", str(tmp_path), 1.0)


def test_resolve_spec_rejects_missing_task_id(tmp_path):
    from courier_worker.host import SpecError

    with pytest.raises(SpecError):
        service.resolve_spec({"dispatch_id": "d1"}, "w1", str(tmp_path), 1.0)


# -- main() argv validation (no run loop) -------------------------------------


def test_main_missing_controller_exits():
    with pytest.raises(SystemExit):
        service.main(["courier_worker.host", "--home", "/tmp"])


def test_main_rejects_max_tasks_not_one():
    with pytest.raises(SystemExit):
        service.main(
            [
                "courier_worker.host",
                "--home",
                "/tmp",
                "--controller",
                "http://127.0.0.1:9",
                "--max-tasks",
                "2",
            ]
        )


def test_main_rejects_bad_heartbeat():
    with pytest.raises(SystemExit):
        service.main(
            [
                "courier_worker.host",
                "--home",
                "/tmp",
                "--controller",
                "http://127.0.0.1:9",
                "--heartbeat",
                "999",
            ]
        )
