"""P9 host_spec: pure spec-validation and constant pins for courier_worker.host.

Targets gaps vs prior P9 host coverage (#346 tests/test_worker_host.py):
that suite pins empty task_id, overlong dispatch_id, general bad
timeout/lease/heartbeat, l2_outcome mapping, retryable mapping, artifacts,
outbox, locks, orphan gate and run_once paths. These tests pin only pure,
offline units with no behavior change and no overlap on file or test names:

- worker_id / result_id / overlong task_id validation (prior suite pins
  empty task_id and overlong dispatch_id only)
- exact timeout / lease / heartbeat boundaries (prior suite pins "bad"
  generally; here the exact MIN/MAX edges are pinned)
- Outcome / LivenessState / bounds constants (not pinned by prior suite)
- ArtifactRef shape and ExecutionResult defaults (prior suite pins mapping
  behavior; here defaults are pinned)
- error-class hierarchy per class (prior suite has one hierarchy test and
  one ResourcePaused test; here each class is pinned distinctly)
- pressure-probe and load return types (prior suite pins never-raises;
  here the return shapes are pinned)
- pure path joining for _run_dir / _claims_dir (prior suite pins claim
  sanitizing; here only joining is pinned, no filesystem writes)

No network, no subprocesses, no filesystem writes, no credentials.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from courier_worker import host
from courier_worker.host import (
    CLAIM_RECORD_GLOB,
    CRASH_REPORT_NAME,
    DEFAULT_TIMEOUT_S,
    KILL_GRACE_S,
    LOAD_PRESSURE_FACTOR,
    MAX_ARGV,
    MAX_ARGV_BYTES,
    MAX_ARTIFACTS,
    MAX_ARTIFACT_BYTES,
    MAX_HEARTBEAT_S,
    MAX_STDIO_TAIL,
    MAX_TIMEOUT_S,
    MIN_HEARTBEAT_S,
    ORPHAN_TERM_GRACE_S,
    OUTBOX_CAP,
    ArtifactRef,
    ContainmentError,
    ExecutionResult,
    ExecutionSpec,
    HostBusy,
    LivenessState,
    OutboxFull,
    Outcome,
    ResourcePaused,
    SpecError,
    _claims_dir,
    _one_minute_load,
    _run_dir,
    default_pressure_probe,
)


def _valid_kwargs(**overrides):
    kwargs = {
        "task_id": "t1",
        "attempt": 1,
        "dispatch_id": "d1",
        "worker_id": "w1",
        "result_id": "r-d1",
        "argv": ["python", "-c", "x"],
        "timeout_s": 10.0,
        "lease_ttl_s": 30.0,
        "artifact_dir": "artifacts/d1",
        "heartbeat_s": 1.0,
    }
    kwargs.update(overrides)
    return kwargs


def _spec(**overrides):
    return ExecutionSpec(**_valid_kwargs(**overrides))


def test_spec_rejects_empty_worker_id():
    with pytest.raises(SpecError):
        _spec(worker_id="")


def test_spec_rejects_empty_result_id():
    with pytest.raises(SpecError):
        _spec(result_id="")


def test_spec_rejects_overlong_task_id():
    with pytest.raises(SpecError):
        _spec(task_id="t" * 201)


def test_spec_rejects_overlong_worker_id():
    with pytest.raises(SpecError):
        _spec(worker_id="w" * 201)


def test_spec_rejects_overlong_result_id():
    with pytest.raises(SpecError):
        _spec(result_id="r" * 201)


def test_spec_rejects_non_string_ids():
    for field in ("task_id", "dispatch_id", "worker_id", "result_id"):
        with pytest.raises(SpecError):
            _spec(**{field: 123})
        with pytest.raises(SpecError):
            _spec(**{field: None})


def test_spec_rejects_float_attempt():
    with pytest.raises(SpecError):
        _spec(attempt=1.5)


def test_spec_rejects_empty_string_argv_entry():
    with pytest.raises(SpecError):
        _spec(argv=["python", ""])


def test_spec_accepts_tuple_argv():
    spec = _spec(argv=("python", "-c", "x"))
    assert tuple(spec.argv) == ("python", "-c", "x")


def test_spec_timeout_boundaries():
    _spec(timeout_s=MAX_TIMEOUT_S)
    _spec(timeout_s=0.5)
    for bad in (0, -1, MAX_TIMEOUT_S + 1.0, "10", None, [10]):
        with pytest.raises(SpecError):
            _spec(timeout_s=bad)


def test_spec_lease_boundaries():
    _spec(lease_ttl_s=1)
    _spec(lease_ttl_s=30.5)
    for bad in (0, 0.5, -3, "30", None):
        with pytest.raises(SpecError):
            _spec(lease_ttl_s=bad)


def test_spec_heartbeat_boundaries():
    _spec(heartbeat_s=MIN_HEARTBEAT_S)
    _spec(heartbeat_s=MAX_HEARTBEAT_S)
    for bad in (MIN_HEARTBEAT_S - 0.01, MAX_HEARTBEAT_S + 0.1, 0, -1, "1.0", None):
        with pytest.raises(SpecError):
            _spec(heartbeat_s=bad)


def test_spec_rejects_non_string_artifact_dir():
    for bad in (None, 123, ["artifacts/d1"]):
        with pytest.raises(SpecError):
            _spec(artifact_dir=bad)


def test_spec_defaults():
    spec = ExecutionSpec(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=["python"],
        timeout_s=5.0,
        lease_ttl_s=10.0,
        artifact_dir="artifacts/d1",
    )
    assert spec.heartbeat_s == 1.0
    assert spec.adapter is None
    assert spec.params is None
    assert spec.effect_key is None


def test_outcome_constants():
    assert Outcome.COMPLETED == "completed"
    assert Outcome.CRASH == "crash"
    assert Outcome.TIMEOUT == "timeout"
    assert Outcome.CANCELLED == "cancelled"
    assert Outcome.LEASE_LOST == "lease-lost"
    assert Outcome.SPAWN_FAILED == "spawn-failed"


def test_liveness_constants():
    assert LivenessState.DELIVERED == "delivered"
    assert LivenessState.ACCEPTED == "accepted"
    assert LivenessState.WORKING == "working"
    assert LivenessState.QUIET == "quiet"
    assert LivenessState.SLOW == "slow"
    assert LivenessState.PROBING == "probing"
    assert LivenessState.FAILED == "failed"
    assert LivenessState.RESULT_DURABLE == "result_durable"
    assert LivenessState.RETIRED == "retired"


def test_bounds_constants():
    assert MAX_TIMEOUT_S == 3600.0
    assert DEFAULT_TIMEOUT_S == 300.0
    assert KILL_GRACE_S == 2.0
    assert MIN_HEARTBEAT_S == 0.2
    assert MAX_HEARTBEAT_S == 30.0
    assert MAX_ARGV == 256
    assert MAX_ARGV_BYTES == 64 * 1024
    assert MAX_ARTIFACTS == 64
    assert MAX_ARTIFACT_BYTES == 16 * 1024 * 1024
    assert MAX_STDIO_TAIL == 64 * 1024
    assert OUTBOX_CAP == 32
    assert ORPHAN_TERM_GRACE_S == 2.0
    assert LOAD_PRESSURE_FACTOR == 4.0
    assert CLAIM_RECORD_GLOB == "dispatch-*.json"
    assert CRASH_REPORT_NAME == "crash.json"


def test_artifact_ref_shape():
    ref = ArtifactRef(path="artifacts/d1/out.txt", sha256="a" * 64)
    assert ref.path == "artifacts/d1/out.txt"
    assert ref.sha256 == "a" * 64


def test_execution_result_defaults():
    spec = _spec()
    result = ExecutionResult(spec=spec, outcome=Outcome.COMPLETED)
    assert result.returncode is None
    assert result.was_signal is False
    assert result.artifacts == ()
    assert result.crash_report_path is None
    assert result.duration_s == 0.0
    assert result.wakes == 0
    assert result.stale is False


def test_l2_outcome_per_outcome():
    spec = _spec()
    for outcome, expected in (
        (Outcome.COMPLETED, "success"),
        (Outcome.CRASH, "failure"),
        (Outcome.TIMEOUT, "failure"),
        (Outcome.CANCELLED, "failure"),
        (Outcome.LEASE_LOST, "failure"),
        (Outcome.SPAWN_FAILED, "failure"),
    ):
        result = ExecutionResult(spec=spec, outcome=outcome)
        assert result.l2_outcome == expected


def test_retryable_per_outcome():
    spec = _spec()
    for outcome, expected in (
        (Outcome.COMPLETED, False),
        (Outcome.CRASH, False),
        (Outcome.TIMEOUT, True),
        (Outcome.CANCELLED, False),
        (Outcome.LEASE_LOST, True),
        (Outcome.SPAWN_FAILED, False),
    ):
        result = ExecutionResult(spec=spec, outcome=outcome)
        assert result.retryable is expected


def test_error_hierarchy_distinct():
    assert issubclass(SpecError, ValueError)
    assert issubclass(HostBusy, RuntimeError)
    assert issubclass(ContainmentError, RuntimeError)
    assert issubclass(ResourcePaused, RuntimeError)
    assert issubclass(OutboxFull, RuntimeError)
    paused = ResourcePaused("cpu-pressure")
    assert paused.reason == "cpu-pressure"
    assert "cpu-pressure" in str(paused)


def test_pressure_probe_return_type():
    outcome = default_pressure_probe()
    assert outcome is None or isinstance(outcome, str)


def test_one_minute_load_return_type():
    outcome = _one_minute_load()
    assert outcome is None or (isinstance(outcome, float) and outcome >= 0.0)


def test_run_dir_claims_dir_joining():
    assert _run_dir("home-x") == Path("home-x") / "run"
    assert _claims_dir("home-x") == Path("home-x") / "run" / "claims"
