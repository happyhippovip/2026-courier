"""P9 hardening: evidence bounds for ``courier_worker.host`` (P9-host-evidence).

Pins two load-bearing evidence helpers that neighboring hardening PRs leave
untouched (their files cover spec rejection, outbox/lock, artifacts, crash
shape, orphan gate and live runs; none pins the digest helper or the
crash-report truncation/rounding bounds):

- ``_sha256_file``: chunked file digest used under artifact collection.
- ``write_crash_report``: the 8000-char ``stderr_tail`` cap, millisecond
  rounding of ``duration_s``, and the missing-stderr empty-tail path.

Tests only; no behavior change. No network, no subprocesses, no ambient
filesystem use beyond ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import json

import pytest

import courier_worker.host as H
from courier_worker.host import ExecutionSpec, Outcome


def _spec(artifact_dir: str) -> ExecutionSpec:
    return ExecutionSpec(
        task_id="task-1",
        attempt=1,
        dispatch_id="d-1",
        worker_id="worker-1",
        result_id="r-d-1",
        argv=("python", "-m", "courier_worker.adapter_runner", "req.json"),
        timeout_s=5.0,
        lease_ttl_s=60.0,
        artifact_dir=artifact_dir,
    )


# -- _sha256_file ------------------------------------------------------------


def test_sha256_empty_file_matches_known_digest(tmp_path):
    target = tmp_path / "empty.bin"
    target.write_bytes(b"")
    assert H._sha256_file(str(target)) == hashlib.sha256(b"").hexdigest()


def test_sha256_known_vector(tmp_path):
    target = tmp_path / "abc.bin"
    target.write_bytes(b"abc")
    assert H._sha256_file(str(target)) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_sha256_spans_multiple_chunks(tmp_path):
    # 200_000 bytes forces several 64 KiB read chunks; the payload is
    # deterministic so the expectation needs no fixture file.
    payload = bytes(range(256)) * 782  # 200_192 bytes
    assert len(payload) > 3 * 65536
    target = tmp_path / "big.bin"
    target.write_bytes(payload)
    assert H._sha256_file(str(target)) == hashlib.sha256(payload).hexdigest()


def test_sha256_missing_file_raises(tmp_path):
    with pytest.raises(OSError):
        H._sha256_file(str(tmp_path / "no-such-file.bin"))


# -- write_crash_report bounds -------------------------------------------------


def test_crash_report_truncates_stderr_tail_to_8000(tmp_path):
    art = tmp_path / "arts"
    art.mkdir()
    err = tmp_path / "s.err"
    err.write_bytes(b"A" * 12000 + b"B" * 8000)
    out = H.write_crash_report(str(art), _spec(str(art)), Outcome.CRASH, 3, 1.5, str(err))
    report = json.loads((art / "crash.json").read_text(encoding="utf-8"))
    assert out == str(art / "crash.json")
    assert report["stderr_tail"] == "B" * 8000


def test_crash_report_rounds_duration_to_milliseconds(tmp_path):
    art = tmp_path / "arts"
    art.mkdir()
    err = tmp_path / "s.err"
    err.write_bytes(b"boom")
    H.write_crash_report(str(art), _spec(str(art)), Outcome.CRASH, 3, 2.3456789, str(err))
    report = json.loads((art / "crash.json").read_text(encoding="utf-8"))
    assert report["duration_s"] == 2.346


def test_crash_report_missing_stderr_yields_empty_tail(tmp_path):
    art = tmp_path / "arts"
    art.mkdir()
    out = H.write_crash_report(
        str(art), _spec(str(art)), Outcome.CRASH, 3, 0.5,
        str(tmp_path / "no-such-stderr.log"),
    )
    report = json.loads((art / "crash.json").read_text(encoding="utf-8"))
    assert out == str(art / "crash.json")
    assert report["stderr_tail"] == ""


def test_crash_report_carries_identity_and_none_returncode(tmp_path):
    art = tmp_path / "arts"
    art.mkdir()
    err = tmp_path / "s.err"
    err.write_bytes(b"boom")
    spec = _spec(str(art))
    H.write_crash_report(str(art), spec, Outcome.CRASH, None, 0.5, str(err))
    report = json.loads((art / "crash.json").read_text(encoding="utf-8"))
    assert report["dispatch_id"] == spec.dispatch_id
    assert report["task_id"] == spec.task_id
    assert report["attempt"] == spec.attempt
    assert report["worker_id"] == spec.worker_id
    assert report["outcome"] == Outcome.CRASH
    assert report["returncode"] is None


def test_crash_report_leaves_no_temp_files(tmp_path):
    art = tmp_path / "arts"
    art.mkdir()
    err = tmp_path / "s.err"
    err.write_bytes(b"boom")
    H.write_crash_report(str(art), _spec(str(art)), Outcome.CRASH, 3, 0.5, str(err))
    names = sorted(p.name for p in art.iterdir())
    assert names == ["crash.json"]
    assert set(json.loads((art / "crash.json").read_text(encoding="utf-8"))) == {
        "dispatch_id", "task_id", "attempt", "worker_id",
        "outcome", "returncode", "duration_s", "stderr_tail",
    }
