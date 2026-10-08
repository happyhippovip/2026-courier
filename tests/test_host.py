"""Dedicated unit tests for courier_worker.host (P9-host).

Complements tests/test_l3_worker_host.py with focused coverage of pure helpers,
spec bounds, artifact/outbox/crash-report paths, and ExecutionResult mapping.
No network. No behavior changes to product code.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

from courier_worker import host as H
from courier_worker.host import (
    ArtifactRef,
    ExecutionResult,
    ExecutionSpec,
    Outcome,
    ResourcePaused,
    SpecError,
    WorkerHost,
    collect_artifacts,
    default_pressure_probe,
    outbox_read_all,
    outbox_remove,
    outbox_write,
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


# -- ExecutionSpec bounds ------------------------------------------------------


def test_spec_rejects_bool_attempt(tmp_path):
    with pytest.raises(SpecError, match="attempt"):
        _spec(tmp_path, attempt=True)  # type: ignore[arg-type]


def test_spec_rejects_non_string_argv_entry(tmp_path):
    with pytest.raises(SpecError, match="argv entries"):
        _spec(tmp_path, argv=(PY, "-c", None))  # type: ignore[arg-type]


def test_spec_rejects_argv_byte_bound(tmp_path):
    huge = "x" * (H.MAX_ARGV_BYTES + 1)
    with pytest.raises(SpecError, match="argv exceeds"):
        _spec(tmp_path, argv=(huge,))


def test_spec_rejects_argv_count_bound(tmp_path):
    with pytest.raises(SpecError, match="argv must be"):
        _spec(tmp_path, argv=tuple(f"a{i}" for i in range(H.MAX_ARGV + 1)))


def test_spec_rejects_heartbeat_out_of_range(tmp_path):
    with pytest.raises(SpecError, match="heartbeat_s"):
        _spec(tmp_path, heartbeat_s=H.MIN_HEARTBEAT_S - 0.01)
    with pytest.raises(SpecError, match="heartbeat_s"):
        _spec(tmp_path, heartbeat_s=H.MAX_HEARTBEAT_S + 0.01)


def test_spec_rejects_empty_artifact_dir(tmp_path):
    with pytest.raises(SpecError, match="artifact_dir"):
        _spec(tmp_path, artifact_dir="")


def test_spec_accepts_optional_adapter_fields(tmp_path):
    spec = _spec(tmp_path, adapter="synthetic", params={"k": 1}, effect_key="ek-1")
    assert spec.adapter == "synthetic"
    assert spec.params == {"k": 1}
    assert spec.effect_key == "ek-1"


# -- ExecutionResult mapping ---------------------------------------------------


def test_execution_result_l2_outcome_and_retryable(tmp_path):
    spec = _spec(tmp_path)
    completed = ExecutionResult(spec=spec, outcome=Outcome.COMPLETED, returncode=0)
    assert completed.l2_outcome == "success"
    assert completed.retryable is False

    timed = ExecutionResult(spec=spec, outcome=Outcome.TIMEOUT, returncode=None)
    assert timed.l2_outcome == "failure"
    assert timed.retryable is True

    lease = ExecutionResult(spec=spec, outcome=Outcome.LEASE_LOST, returncode=None)
    assert lease.retryable is True

    crash = ExecutionResult(spec=spec, outcome=Outcome.CRASH, returncode=1)
    assert crash.retryable is False

    cancelled = ExecutionResult(spec=spec, outcome=Outcome.CANCELLED, returncode=None)
    assert cancelled.retryable is False


# -- ResourcePaused ------------------------------------------------------------


def test_resource_paused_reason_tag():
    err = ResourcePaused("fd-exhaustion")
    assert err.reason == "fd-exhaustion"
    assert "RESOURCE_PAUSE" in str(err)


# -- artifacts -----------------------------------------------------------------


def test_collect_artifacts_missing_dir_is_empty(tmp_path):
    assert collect_artifacts(str(tmp_path / "missing")) == ()


def test_collect_artifacts_hashes_sorted_relative_paths(tmp_path):
    root = tmp_path / "arts"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_bytes(b"aaa")
    (root / "sub" / "b.txt").write_bytes(b"bbb")
    refs = collect_artifacts(str(root))
    assert [r.path for r in refs] == ["a.txt", os.path.join("sub", "b.txt")]
    assert all(isinstance(r, ArtifactRef) and len(r.sha256) == 64 for r in refs)


def test_collect_artifacts_count_bound_fails_closed(tmp_path, monkeypatch):
    root = tmp_path / "arts"
    root.mkdir()
    for i in range(3):
        (root / f"f{i}.txt").write_bytes(b"x")
    monkeypatch.setattr(H, "MAX_ARTIFACTS", 2)
    with pytest.raises(H.ContainmentError, match="artifact set exceeds"):
        collect_artifacts(str(root))


def test_collect_artifacts_byte_bound_fails_closed(tmp_path, monkeypatch):
    root = tmp_path / "arts"
    root.mkdir()
    (root / "big.bin").write_bytes(b"0123456789")
    monkeypatch.setattr(H, "MAX_ARTIFACT_BYTES", 5)
    with pytest.raises(H.ContainmentError, match="artifact set exceeds"):
        collect_artifacts(str(root))


# -- crash report / stdio tail -------------------------------------------------


def test_write_crash_report_persists_identity_and_stderr_tail(tmp_path):
    art = tmp_path / "artifacts" / "d1"
    art.mkdir(parents=True)
    err = tmp_path / "run" / "task-d1.err"
    err.parent.mkdir(parents=True)
    err.write_bytes(b"line-one\nline-two\n")
    spec = _spec(tmp_path, artifact_dir=str(art))
    path = write_crash_report(str(art), spec, Outcome.CRASH, 1, 1.2345, str(err))
    assert path.endswith(H.CRASH_REPORT_NAME)
    data = json.loads((art / H.CRASH_REPORT_NAME).read_text(encoding="utf-8"))
    assert data["dispatch_id"] == "d1"
    assert data["task_id"] == "t1"
    assert data["attempt"] == 1
    assert data["worker_id"] == "w1"
    assert data["outcome"] == Outcome.CRASH
    assert data["returncode"] == 1
    assert data["duration_s"] == 1.234
    assert "line-two" in data["stderr_tail"]


def test_tail_missing_path_is_empty(tmp_path):
    assert H._tail(str(tmp_path / "nope.err")) == ""


def test_tail_respects_byte_limit(tmp_path):
    path = tmp_path / "big.err"
    path.write_bytes(b"abcdefghij")
    assert H._tail(str(path), limit=4) == "ghij"


# -- outbox --------------------------------------------------------------------


def test_outbox_write_read_remove_roundtrip(tmp_path):
    payload = {"dispatch_id": "d9", "outcome": "success"}
    path = outbox_write(str(tmp_path), payload)
    assert path.name == "d9.json"
    items = outbox_read_all(str(tmp_path))
    assert len(items) == 1
    assert items[0][1]["dispatch_id"] == "d9"
    outbox_remove(str(tmp_path), "d9")
    assert outbox_read_all(str(tmp_path)) == []


def test_outbox_read_skips_corrupt_json(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "good.json").write_text('{"dispatch_id":"g"}', encoding="utf-8")
    (outbox / "bad.json").write_text("{not-json", encoding="utf-8")
    items = outbox_read_all(str(tmp_path))
    assert [p["dispatch_id"] for _, p in items] == ["g"]


def test_outbox_remove_missing_is_silent(tmp_path):
    outbox_remove(str(tmp_path), "never-written")


def test_outbox_read_all_missing_dir(tmp_path):
    assert outbox_read_all(str(tmp_path / "absent-home")) == []


# -- claim path / orphan gate --------------------------------------------------


def test_claim_path_sanitizes_dispatch_id(tmp_path):
    path = H._claim_path(str(tmp_path), "weird/id:one")
    assert path.name == "dispatch-weird_id_one.json"
    assert ".." not in path.name


def test_orphan_gate_no_claims_dir(tmp_path):
    assert run_orphan_gate(str(tmp_path)) == 0


def test_orphan_gate_quarantines_corrupt_record(tmp_path):
    claims = tmp_path / "run" / "claims"
    claims.mkdir(parents=True)
    bad = claims / "dispatch-bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    assert run_orphan_gate(str(tmp_path)) == 0
    assert not bad.exists()
    assert (claims / "dispatch-bad.json.corrupt").exists()


def test_orphan_gate_leaves_live_owner(tmp_path):
    claims = tmp_path / "run" / "claims"
    claims.mkdir(parents=True)
    record = {
        "task_id": "t",
        "attempt": 1,
        "dispatch_id": "live-1",
        "worker_id": "w",
        "owner_pid": os.getpid(),
        "child_pid": 0,
        "pgid": None,
    }
    path = claims / "dispatch-live-1.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    assert run_orphan_gate(str(tmp_path)) == 0
    assert path.exists()


# -- pressure probe / host busy ------------------------------------------------


def test_default_pressure_probe_returns_none_or_reason_string():
    reason = default_pressure_probe()
    assert reason is None or isinstance(reason, str)


def test_host_busy_property_toggles_with_active(tmp_path):
    host = WorkerHost(str(tmp_path), pressure_probe=lambda: None)
    assert host.busy is False
    host._active = "d1"
    assert host.busy is True
    host._active = None
    assert host.busy is False


def test_heartbeat_exception_does_not_kill_run(tmp_path):
    host = WorkerHost(str(tmp_path), pressure_probe=lambda: None)
    art = tmp_path / "artifacts" / "hb"
    art.mkdir(parents=True)
    spec = _spec(
        tmp_path,
        dispatch_id="hb1",
        result_id="r-hb1",
        artifact_dir=str(art),
        argv=(PY, "-c", "import time; time.sleep(0.4)"),
        heartbeat_s=0.2,
    )

    def boom(_elapsed: float):
        raise RuntimeError("probe noise")

    result = host.run_once(spec, on_heartbeat=boom)
    assert result.outcome == Outcome.COMPLETED
    assert result.returncode == 0
