"""Hardening tests for the durable outbox + home-lock corner of courier_worker.host.

Angle (P9-host_outbox): the undelivered-result outbox queue, the fail-closed
home lock, owner-liveness probing, and claim-record shape. This deliberately
avoids the ExecutionSpec-validation / artifact / tail surface covered by the
parallel P9-host effort. Tests only; no behavior change.
"""

import dataclasses
import json
import os
from types import SimpleNamespace

import pytest

from courier_worker import host as H
from courier_worker.host import (
    ArtifactRef,
    ExecutionSpec,
    HostBusy,
    LivenessState,
    OutboxFull,
    Outcome,
)


def _spec(**over):
    kwargs = dict(
        task_id="task-1",
        attempt=1,
        dispatch_id="dispatch-1",
        worker_id="worker-1",
        result_id="result-1",
        argv=["echo", "hi"],
        timeout_s=30.0,
        lease_ttl_s=60.0,
        artifact_dir="artifacts",
    )
    kwargs.update(over)
    return ExecutionSpec(**kwargs)


def _payload(dispatch_id="dispatch-1", **over):
    payload = {"dispatch_id": dispatch_id, "outcome": Outcome.COMPLETED, "attempt": 1}
    payload.update(over)
    return payload


def test_home_layout_helpers(tmp_path):
    home = str(tmp_path)
    assert H._run_dir(home) == tmp_path / "run"
    assert H._claims_dir(home) == tmp_path / "run" / "claims"
    assert H._outbox_dir(home) == tmp_path / "outbox"


def test_outbox_write_then_read_roundtrip(tmp_path):
    home = str(tmp_path)
    payload = _payload(result_id="result-9")
    path = H.outbox_write(home, payload)
    assert path.parent == tmp_path / "outbox"
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    pending = H.outbox_read_all(home)
    assert len(pending) == 1
    assert pending[0][1] == payload


def test_outbox_write_same_dispatch_overwrites(tmp_path):
    home = str(tmp_path)
    H.outbox_write(home, _payload(outcome=Outcome.TIMEOUT))
    H.outbox_write(home, _payload(outcome=Outcome.COMPLETED))
    pending = H.outbox_read_all(home)
    assert len(pending) == 1
    assert pending[0][1]["outcome"] == Outcome.COMPLETED


def test_outbox_cap_rejects_new_dispatch_but_allows_rewrite(tmp_path):
    home = str(tmp_path)
    for i in range(H.OUTBOX_CAP):
        H.outbox_write(home, _payload(dispatch_id=f"dispatch-{i}"))
    with pytest.raises(OutboxFull):
        H.outbox_write(home, _payload(dispatch_id="dispatch-overflow"))
    # Re-delivering an already-queued dispatch must still succeed at cap.
    H.outbox_write(home, _payload(dispatch_id="dispatch-0", attempt=2))
    assert len(H.outbox_read_all(home)) == H.OUTBOX_CAP


def test_outbox_read_all_missing_dir_is_empty(tmp_path):
    assert H.outbox_read_all(str(tmp_path / "no-such-home")) == []


def test_outbox_read_all_skips_corrupt_files(tmp_path):
    home = str(tmp_path)
    H.outbox_write(home, _payload())
    (tmp_path / "outbox" / "broken.json").write_text("{not json", encoding="utf-8")
    pending = H.outbox_read_all(home)
    assert [p for _, p in pending] == [_payload()]


def test_outbox_remove_deletes_and_missing_is_noop(tmp_path):
    home = str(tmp_path)
    H.outbox_write(home, _payload())
    H.outbox_remove(home, "dispatch-1")
    assert H.outbox_read_all(home) == []
    H.outbox_remove(home, "dispatch-1")  # must not raise
    H.outbox_remove(home, "dispatch-missing")


def test_acquire_home_lock_writes_owner_pid(tmp_path):
    home = str(tmp_path)
    fd = H.acquire_home_lock(home)
    try:
        lock_path = tmp_path / "run" / "worker.lock"
        assert lock_path.read_text(encoding="utf-8") == str(os.getpid())
    finally:
        H.release_home_lock(fd)


def test_second_acquire_while_held_raises_host_busy(tmp_path):
    home = str(tmp_path)
    fd = H.acquire_home_lock(home)
    try:
        with pytest.raises(HostBusy):
            H.acquire_home_lock(home)
    finally:
        H.release_home_lock(fd)
    # After release the home can be owned again.
    fd2 = H.acquire_home_lock(home)
    H.release_home_lock(fd2)


def test_owner_alive_for_self_and_rejects_bad_pids():
    assert H._owner_alive(os.getpid()) is True
    assert H._owner_alive(0) is False
    assert H._owner_alive(-3) is False
    assert H._owner_alive(999999) is False


def test_write_claim_record_shape(tmp_path):
    home = str(tmp_path)
    spec = _spec()
    run = SimpleNamespace(pid=4242, group_id=lambda: 4242)
    path = H._write_claim_record(home, spec, run)
    assert path.parent == tmp_path / "run" / "claims"
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["task_id"] == "task-1"
    assert record["attempt"] == 1
    assert record["dispatch_id"] == "dispatch-1"
    assert record["worker_id"] == "worker-1"
    assert record["owner_pid"] == os.getpid()
    assert record["child_pid"] == 4242
    assert record["pgid"] == 4242


def test_outcome_and_liveness_values_are_distinct_strings():
    outcomes = [Outcome.COMPLETED, Outcome.CRASH, Outcome.TIMEOUT,
                Outcome.CANCELLED, Outcome.LEASE_LOST, Outcome.SPAWN_FAILED]
    assert all(isinstance(v, str) and v for v in outcomes)
    assert len(set(outcomes)) == len(outcomes)
    states = [LivenessState.DELIVERED, LivenessState.ACCEPTED, LivenessState.WORKING,
              LivenessState.QUIET, LivenessState.SLOW, LivenessState.PROBING,
              LivenessState.FAILED, LivenessState.RESULT_DURABLE, LivenessState.RETIRED]
    assert all(isinstance(v, str) and v for v in states)
    assert len(set(states)) == len(states)


def test_artifact_ref_is_frozen_value():
    ref = ArtifactRef(path="out/log.txt", sha256="abc")
    assert ref == ArtifactRef(path="out/log.txt", sha256="abc")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.path = "other"
