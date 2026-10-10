"""P9 host groundwork pins: claim records, orphan gate, artifact collection.

Tests-only hardening for :mod:`courier_worker.host` (no behavior change).
Covers the offline units that need no child process, no signals to live
trees and no network: claim-path sanitising, atomic claim-record writes,
the orphan gate's fail-closed dispositions, owner liveness, artifact
collection bounds, stdio tailing and the pre-spawn pressure guard of
:meth:`WorkerHost.run_once`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from types import SimpleNamespace

import pytest

import courier_worker.host as H
from courier_worker.host import (
    ContainmentError,
    ExecutionSpec,
    ResourcePaused,
    WorkerHost,
)


def make_spec(tmp_path, **overrides):
    fields = {
        "task_id": "task-1",
        "attempt": 1,
        "dispatch_id": "dispatch-1",
        "worker_id": "worker-1",
        "result_id": "result-1",
        "argv": [sys.executable, "-c", "pass"],
        "timeout_s": 5.0,
        "lease_ttl_s": 60.0,
        "artifact_dir": str(tmp_path / "artifacts"),
        "heartbeat_s": 1.0,
    }
    fields.update(overrides)
    return ExecutionSpec(**fields)


def make_run(pid=12345, pgid=12345):
    return SimpleNamespace(pid=pid, group_id=lambda: pgid)


# -- claim paths ---------------------------------------------------------------

def test_claim_path_sanitizes_unsafe_chars(tmp_path):
    path = H._claim_path(str(tmp_path), "a/b\\c:d e*f")
    assert path.parent == tmp_path / "run" / "claims"
    assert path.name.startswith("dispatch-")
    assert path.suffix == ".json"
    stem = path.name[len("dispatch-"):-len(".json")]
    assert stem and all(c.isalnum() or c in "-_." for c in stem)


def test_claim_path_empty_dispatch_uses_unnamed(tmp_path):
    path = H._claim_path(str(tmp_path), "")
    assert path.name == "dispatch-unnamed.json"


def test_claim_path_keeps_safe_chars(tmp_path):
    path = H._claim_path(str(tmp_path), "abc-123_X.y")
    assert path.name == "dispatch-abc-123_X.y.json"


# -- claim records ---------------------------------------------------------------

def test_write_claim_record_shape(tmp_path):
    home = tmp_path / "home"
    spec = make_spec(tmp_path)
    record_path = H._write_claim_record(str(home), spec, make_run())
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert set(record) == {
        "task_id", "attempt", "dispatch_id", "worker_id",
        "owner_pid", "child_pid", "pgid",
    }
    assert record["task_id"] == "task-1"
    assert record["attempt"] == 1
    assert record["dispatch_id"] == "dispatch-1"
    assert record["worker_id"] == "worker-1"
    assert record["owner_pid"] == os.getpid()
    assert record["child_pid"] == 12345
    assert record["pgid"] == 12345


def test_write_claim_record_leaves_no_temp_files(tmp_path):
    home = tmp_path / "home"
    spec = make_spec(tmp_path)
    H._write_claim_record(str(home), spec, make_run())
    names = [p.name for p in (home / "run" / "claims").iterdir()]
    assert names == ["dispatch-dispatch-1.json"]


def test_write_claim_record_replace_is_atomic(tmp_path):
    home = tmp_path / "home"
    spec = make_spec(tmp_path)
    first = H._write_claim_record(str(home), spec, make_run(pid=111))
    second = H._write_claim_record(str(home), spec, make_run(pid=222))
    assert first == second
    record = json.loads(second.read_text(encoding="utf-8"))
    assert record["child_pid"] == 222


# -- owner liveness ---------------------------------------------------------------

def test_owner_alive_self_and_nonpositive():
    assert H._owner_alive(os.getpid()) is True
    assert H._owner_alive(0) is False
    assert H._owner_alive(-3) is False


# -- orphan gate ---------------------------------------------------------------

def _write_raw_claim(home, dispatch_id, payload):
    claims = home / "run" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    path = claims / f"dispatch-{dispatch_id}.json"
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_orphan_gate_missing_claims_dir_returns_zero(tmp_path):
    assert H.run_orphan_gate(str(tmp_path / "home")) == 0


def test_orphan_gate_corrupt_record_renamed_not_counted(tmp_path):
    home = tmp_path / "home"
    bad = _write_raw_claim(home, "x", "{not json")
    assert H.run_orphan_gate(str(home)) == 0
    assert not bad.exists()
    assert (bad.parent / "dispatch-x.json.corrupt").exists()


def test_orphan_gate_live_owner_hands_off(tmp_path):
    home = tmp_path / "home"
    path = _write_raw_claim(home, "live", {"owner_pid": os.getpid()})
    assert H.run_orphan_gate(str(home)) == 0
    assert path.exists()


def test_orphan_gate_dead_owner_without_tree_reaps_record(tmp_path):
    home = tmp_path / "home"
    path = _write_raw_claim(home, "dead", {"owner_pid": 0})
    assert H.run_orphan_gate(str(home)) == 1
    assert not path.exists()


# -- artifacts ---------------------------------------------------------------

def test_collect_artifacts_missing_dir_is_empty(tmp_path):
    assert H.collect_artifacts(str(tmp_path / "nope")) == ()


def test_collect_artifacts_hashes_with_relative_paths(tmp_path):
    root = tmp_path / "artifacts"
    (root / "sub").mkdir(parents=True)
    (root / "b.txt").write_bytes(b"bee")
    (root / "a.txt").write_bytes(b"ay")
    (root / "sub" / "c.txt").write_bytes(b"see")
    refs = H.collect_artifacts(str(root))
    by_path = {r.path: r.sha256 for r in refs}
    assert set(by_path) == {"a.txt", "b.txt", os.path.join("sub", "c.txt")}
    assert by_path["a.txt"] == hashlib.sha256(b"ay").hexdigest()
    assert by_path["b.txt"] == hashlib.sha256(b"bee").hexdigest()


def test_collect_artifacts_empty_file_known_digest(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "empty.bin").write_bytes(b"")
    (ref,) = H.collect_artifacts(str(root))
    assert ref.sha256 == hashlib.sha256(b"").hexdigest()


def test_collect_artifacts_count_bound_is_fail_closed(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    for i in range(H.MAX_ARTIFACTS + 1):
        (root / f"f{i:03d}.txt").write_bytes(b"x")
    with pytest.raises(ContainmentError):
        H.collect_artifacts(str(root))


def test_collect_artifacts_bytes_bound_is_fail_closed(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "one.bin").write_bytes(b"12345678")
    (root / "two.bin").write_bytes(b"12345678")
    monkeypatch.setattr(H, "MAX_ARTIFACT_BYTES", 10)
    with pytest.raises(ContainmentError):
        H.collect_artifacts(str(root))


# -- stdio tail ------------------------------------------------------------------

def test_tail_missing_file_is_empty(tmp_path):
    assert H._tail(str(tmp_path / "nope")) == ""


def test_tail_returns_whole_short_file(tmp_path):
    path = tmp_path / "out.err"
    path.write_bytes(b"hello")
    assert H._tail(str(path)) == "hello"


def test_tail_respects_limit(tmp_path):
    path = tmp_path / "out.err"
    path.write_bytes(b"x" * 100 + b"END")
    assert H._tail(str(path), limit=10) == "x" * 7 + "END"


# -- pre-spawn host guards ---------------------------------------------------------

def test_host_starts_idle(tmp_path):
    assert WorkerHost(str(tmp_path / "home")).busy is False


def test_run_once_pressure_pause_raises_before_spawn(tmp_path):
    home = tmp_path / "home"
    host = WorkerHost(str(home), pressure_probe=lambda: "test-pause")
    with pytest.raises(ResourcePaused) as excinfo:
        host.run_once(make_spec(tmp_path))
    assert excinfo.value.reason == "test-pause"
    assert host.busy is False
