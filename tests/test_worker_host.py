"""Dedicated hardening tests for courier_worker.host (P9-host).

Complements the lane integration suite in tests/test_l3_worker_host.py with
focused unit coverage of spec validation, result mapping, artifact/outbox
helpers, claim-path hygiene, orphan-gate bookkeeping and the single-flight
host. No network. No behavior changes to product code.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import pytest

from courier_worker import host as H
from courier_worker.host import (
    ArtifactRef,
    ContainmentError,
    ExecutionResult,
    ExecutionSpec,
    HostBusy,
    OutboxFull,
    Outcome,
    ResourcePaused,
    SpecError,
    WorkerHost,
    acquire_home_lock,
    collect_artifacts,
    default_pressure_probe,
    outbox_read_all,
    outbox_remove,
    outbox_write,
    release_home_lock,
    run_orphan_gate,
    write_crash_report,
)

PY = sys.executable


def _spec(tmp_path, **over) -> ExecutionSpec:
    kw = dict(
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r-d1",
        argv=(PY, "-c", "pass"),
        timeout_s=30.0,
        lease_ttl_s=30.0,
        artifact_dir=str(tmp_path / "artifacts" / "d1"),
        heartbeat_s=1.0,
    )
    kw.update(over)
    return ExecutionSpec(**kw)


# -- ExecutionSpec validation -------------------------------------------------


def test_spec_rejects_bool_attempt(tmp_path):
    with pytest.raises(SpecError, match="attempt"):
        _spec(tmp_path, attempt=True)  # type: ignore[arg-type]


def test_spec_rejects_attempt_below_one(tmp_path):
    with pytest.raises(SpecError, match="attempt"):
        _spec(tmp_path, attempt=0)


def test_spec_rejects_empty_task_id(tmp_path):
    with pytest.raises(SpecError, match="task_id"):
        _spec(tmp_path, task_id="")


def test_spec_rejects_overlong_dispatch_id(tmp_path):
    with pytest.raises(SpecError, match="dispatch_id"):
        _spec(tmp_path, dispatch_id="x" * 201)


def test_spec_rejects_empty_argv(tmp_path):
    with pytest.raises(SpecError, match="argv"):
        _spec(tmp_path, argv=())


def test_spec_rejects_too_many_argv(tmp_path):
    with pytest.raises(SpecError, match="argv"):
        _spec(tmp_path, argv=tuple(f"a{i}" for i in range(H.MAX_ARGV + 1)))


def test_spec_rejects_non_string_argv_entry(tmp_path):
    with pytest.raises(SpecError, match="argv entries"):
        _spec(tmp_path, argv=(PY, "x", None))  # type: ignore[list-item]


def test_spec_rejects_oversize_argv_bytes(tmp_path):
    huge = "x" * (H.MAX_ARGV_BYTES + 1)
    with pytest.raises(SpecError, match="argv exceeds"):
        _spec(tmp_path, argv=(huge,))


def test_spec_rejects_bad_timeout(tmp_path):
    with pytest.raises(SpecError, match="timeout_s"):
        _spec(tmp_path, timeout_s=0)
    with pytest.raises(SpecError, match="timeout_s"):
        _spec(tmp_path, timeout_s=H.MAX_TIMEOUT_S + 1)


def test_spec_rejects_bad_lease(tmp_path):
    with pytest.raises(SpecError, match="lease_ttl_s"):
        _spec(tmp_path, lease_ttl_s=0)


def test_spec_rejects_bad_heartbeat(tmp_path):
    with pytest.raises(SpecError, match="heartbeat_s"):
        _spec(tmp_path, heartbeat_s=H.MIN_HEARTBEAT_S - 0.01)
    with pytest.raises(SpecError, match="heartbeat_s"):
        _spec(tmp_path, heartbeat_s=H.MAX_HEARTBEAT_S + 1)


def test_spec_rejects_empty_artifact_dir(tmp_path):
    with pytest.raises(SpecError, match="artifact_dir"):
        _spec(tmp_path, artifact_dir="")


def test_spec_defaults_heartbeat(tmp_path):
    spec = _spec(tmp_path)
    assert spec.heartbeat_s == 1.0
    assert spec.adapter is None


# -- result mapping and error types -------------------------------------------


def test_l2_outcome_mapping(tmp_path):
    spec = _spec(tmp_path)
    assert ExecutionResult(spec=spec, outcome=Outcome.COMPLETED).l2_outcome == "success"
    for outcome in (
        Outcome.CRASH,
        Outcome.TIMEOUT,
        Outcome.CANCELLED,
        Outcome.LEASE_LOST,
        Outcome.SPAWN_FAILED,
    ):
        assert ExecutionResult(spec=spec, outcome=outcome).l2_outcome == "failure"


def test_retryable_only_for_timeout_and_lease_lost(tmp_path):
    spec = _spec(tmp_path)
    assert ExecutionResult(spec=spec, outcome=Outcome.TIMEOUT).retryable is True
    assert ExecutionResult(spec=spec, outcome=Outcome.LEASE_LOST).retryable is True
    for outcome in (Outcome.COMPLETED, Outcome.CRASH, Outcome.CANCELLED, Outcome.SPAWN_FAILED):
        assert ExecutionResult(spec=spec, outcome=outcome).retryable is False


def test_error_hierarchy():
    assert issubclass(SpecError, ValueError)
    assert issubclass(HostBusy, RuntimeError)
    assert issubclass(ContainmentError, RuntimeError)
    assert issubclass(ResourcePaused, RuntimeError)
    assert issubclass(OutboxFull, RuntimeError)


def test_resource_paused_carries_reason():
    err = ResourcePaused("cpu-pressure")
    assert err.reason == "cpu-pressure"
    assert "cpu-pressure" in str(err)


def test_pressure_probe_never_raises():
    result = default_pressure_probe()
    assert result is None or isinstance(result, str)


# -- artifacts, tails and crash reports ---------------------------------------


def test_collect_artifacts_missing_and_empty(tmp_path):
    assert collect_artifacts(str(tmp_path / "nope")) == ()
    empty = tmp_path / "empty"
    empty.mkdir()
    assert collect_artifacts(str(empty)) == ()


def test_collect_artifacts_hashes_files(tmp_path):
    root = tmp_path / "arts"
    root.mkdir()
    (root / "b.txt").write_bytes(b"bee")
    (root / "a.txt").write_bytes(b"aye")
    found = collect_artifacts(str(root))
    by_path = {a.path: a.sha256 for a in found}
    assert by_path["a.txt"] == hashlib.sha256(b"aye").hexdigest()
    assert by_path["b.txt"] == hashlib.sha256(b"bee").hexdigest()
    assert all(isinstance(a, ArtifactRef) for a in found)


def test_collect_artifacts_count_bound(tmp_path):
    root = tmp_path / "many"
    root.mkdir()
    for i in range(H.MAX_ARTIFACTS + 1):
        (root / f"f{i:03d}.txt").write_bytes(b"x")
    with pytest.raises(ContainmentError, match="exceeds bounds"):
        collect_artifacts(str(root))


def test_tail_missing_returns_empty(tmp_path):
    assert H._tail(str(tmp_path / "missing.out")) == ""


def test_tail_respects_limit(tmp_path):
    path = tmp_path / "s.out"
    path.write_bytes(b"0123456789")
    assert H._tail(str(path), limit=4) == "6789"


def test_write_crash_report_shape(tmp_path):
    spec = _spec(tmp_path)
    art = tmp_path / "arts"
    art.mkdir()
    err = tmp_path / "s.err"
    err.write_bytes(b"boom")
    out = write_crash_report(str(art), spec, Outcome.CRASH, 3, 1.234, str(err))
    assert out.endswith("crash.json")
    report = json.loads(open(out, encoding="utf-8").read())
    assert report["dispatch_id"] == "d1"
    assert report["outcome"] == Outcome.CRASH
    assert report["returncode"] == 3
    assert report["stderr_tail"] == "boom"


def test_claim_path_sanitizes_separators(tmp_path):
    path = H._claim_path(str(tmp_path), "a/b\\c:d")
    assert path.name.startswith("dispatch-")
    assert "/" not in path.name and "\\" not in path.name and ":" not in path.name


# -- orphan gate ---------------------------------------------------------------


def test_orphan_gate_without_claims_dir(tmp_path):
    assert run_orphan_gate(str(tmp_path / "home")) == 0


def test_orphan_gate_renames_corrupt_record(tmp_path):
    claims = tmp_path / "home" / "run" / "claims"
    claims.mkdir(parents=True)
    bad = claims / "dispatch-x.json"
    bad.write_text("{not json", encoding="utf-8")
    assert run_orphan_gate(str(tmp_path / "home")) == 0
    assert (claims / "dispatch-x.json.corrupt").exists()


def test_orphan_gate_skips_live_owner(tmp_path):
    claims = tmp_path / "home" / "run" / "claims"
    claims.mkdir(parents=True)
    rec = claims / "dispatch-live.json"
    rec.write_text(json.dumps({"owner_pid": os.getpid(), "child_pid": 0}), encoding="utf-8")
    assert run_orphan_gate(str(tmp_path / "home")) == 0
    assert rec.exists()


def test_orphan_gate_reaps_dead_owner_without_tree(tmp_path):
    claims = tmp_path / "home" / "run" / "claims"
    claims.mkdir(parents=True)
    rec = claims / "dispatch-dead.json"
    rec.write_text(json.dumps({"owner_pid": -5, "child_pid": 0}), encoding="utf-8")
    assert run_orphan_gate(str(tmp_path / "home")) == 1
    assert not rec.exists()


# -- home lock -----------------------------------------------------------------


def test_home_lock_single_owner(tmp_path):
    home = str(tmp_path / "home")
    fd = acquire_home_lock(home)
    try:
        with pytest.raises(HostBusy):
            acquire_home_lock(home)
    finally:
        release_home_lock(fd)
    fd2 = acquire_home_lock(home)
    release_home_lock(fd2)


# -- outbox --------------------------------------------------------------------


def test_outbox_roundtrip_and_remove(tmp_path):
    home = str(tmp_path / "home")
    payload = {"dispatch_id": "d1", "result": 1}
    outbox_write(home, payload)
    items = outbox_read_all(home)
    assert len(items) == 1
    assert items[0][1] == payload
    outbox_remove(home, "d1")
    assert outbox_read_all(home) == []


def test_outbox_cap_allows_overwrite_but_blocks_new(tmp_path):
    home = str(tmp_path / "home")
    for i in range(H.OUTBOX_CAP):
        outbox_write(home, {"dispatch_id": f"d{i}", "n": i})
    outbox_write(home, {"dispatch_id": "d0", "n": 999})
    with pytest.raises(OutboxFull):
        outbox_write(home, {"dispatch_id": "overflow", "n": -1})


# -- single-flight host ----------------------------------------------------------


def test_host_pressure_pause_leaves_host_idle(tmp_path):
    host = WorkerHost(str(tmp_path / "home"), pressure_probe=lambda: "cpu-pressure")
    assert host.busy is False
    with pytest.raises(ResourcePaused):
        host.run_once(_spec(tmp_path))
    assert host.busy is False


def test_host_rejects_second_dispatch_while_busy(tmp_path):
    host = WorkerHost(str(tmp_path / "home"))
    host._active = "d-busy"  # simulate an owned live dispatch
    try:
        with pytest.raises(HostBusy):
            host.run_once(_spec(tmp_path))
    finally:
        host._active = None


def test_host_run_once_success(tmp_path):
    home = str(tmp_path / "home")
    host = WorkerHost(home)
    result = host.run_once(_spec(tmp_path))
    assert result.outcome == Outcome.COMPLETED
    assert result.returncode == 0
    assert result.l2_outcome == "success"
    assert result.retryable is False
    assert result.crash_report_path is None
    assert result.wakes >= 1
    assert host.busy is False


def test_host_run_once_crash_records_report(tmp_path):
    home = str(tmp_path / "home")
    host = WorkerHost(home)
    spec = _spec(tmp_path, argv=(PY, "-c", "raise SystemExit(3)"))
    result = host.run_once(spec)
    assert result.outcome == Outcome.CRASH
    assert result.returncode == 3
    assert result.retryable is False
    assert result.crash_report_path is not None
    assert result.crash_report_path.endswith("crash.json")


def test_host_run_once_cancelled(tmp_path):
    home = str(tmp_path / "home")
    host = WorkerHost(home)
    spec = _spec(tmp_path, argv=(PY, "-c", "import time; time.sleep(30)"))
    result = host.run_once(spec, is_cancelled=lambda: True)
    assert result.outcome == Outcome.CANCELLED
    assert result.retryable is False


def test_host_heartbeat_exception_does_not_kill_run(tmp_path):
    home = str(tmp_path / "home")
    host = WorkerHost(home)

    def _boom(_elapsed: float):
        raise RuntimeError("heartbeat failed")

    result = host.run_once(_spec(tmp_path), on_heartbeat=_boom)
    assert result.outcome == Outcome.COMPLETED


def test_host_run_once_timeout_is_retryable(tmp_path):
    home = str(tmp_path / "home")
    host = WorkerHost(home)
    spec = _spec(
        tmp_path,
        argv=(PY, "-c", "import time; time.sleep(30)"),
        timeout_s=0.5,
        lease_ttl_s=60.0,
        heartbeat_s=0.2,
    )
    result = host.run_once(spec)
    assert result.outcome == Outcome.TIMEOUT
    assert result.retryable is True
