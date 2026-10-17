"""L3 run-dir stdio retention (lane L3).

Every run leaves ``task-<dispatch>.out/.err`` in ``<home>/run``. Without a
bound the home grows forever (on Windows: inside %LOCALAPPDATA%). The host
prunes the oldest pairs at run start and keeps the newest
``RUN_STDIO_RETAIN_PAIRS`` for debugging. Durable evidence (crash report,
artifacts) lives per dispatch and is never pruned.

Nothing here touches the live journal, the network, or another lane's files.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

from courier_worker import host as H
from courier_worker.host import ExecutionSpec, Outcome, WorkerHost

PY = sys.executable


@pytest.fixture(autouse=True)
def windows_teardown_delay():
    yield
    if os.name == "nt":
        time.sleep(0.1)


def make_spec(home, name="t1", attempt=1, dispatch="d1", argv=None, **over):
    kw = dict(task_id=name, attempt=attempt, dispatch_id=dispatch, worker_id="w1",
              result_id="r-" + dispatch,
              argv=tuple(argv if argv is not None else [PY, "-c", "pass"]),
              timeout_s=30.0, lease_ttl_s=30.0,
              artifact_dir=os.path.join(str(home), "artifacts", dispatch), heartbeat_s=0.2)
    kw.update(over)
    return ExecutionSpec(**kw)


def make_host(home):
    return WorkerHost(str(home), pressure_probe=lambda: None)


def _seed_pair(run_dir, tag, mtime, out=b"x", err=b""):
    for suffix, data in ((".out", out), (".err", err)):
        path = os.path.join(run_dir, f"task-{tag}{suffix}")
        with open(path, "wb") as fh:
            fh.write(data)
        os.utime(path, (mtime, mtime))


def _tags(run_dir):
    tags = set()
    for name in os.listdir(run_dir):
        if name.startswith("task-") and (name.endswith(".out") or name.endswith(".err")):
            tags.add(name[:-len(".out")])
    return tags


def test_prune_keeps_newest_pairs_and_ignores_other_files(tmp_path):
    run_dir = str(tmp_path / "run")
    os.makedirs(os.path.join(run_dir, "claims"))
    base = time.time() - 1000.0
    for i in range(12):
        _seed_pair(run_dir, f"old-{i:02d}", base + i)
    # Non-stdio files must never be touched.
    lock_path = os.path.join(run_dir, "worker.lock")
    with open(lock_path, "wb") as fh:
        fh.write(b"1234")
    claim_path = os.path.join(run_dir, "claims", "dispatch-x.json")
    with open(claim_path, "wb") as fh:
        fh.write(b"{}")
    notes_path = os.path.join(run_dir, "notes.txt")
    with open(notes_path, "wb") as fh:
        fh.write(b"keep me")

    pruned = H._prune_run_stdio(run_dir)

    assert pruned == 2 * (12 - H.RUN_STDIO_RETAIN_PAIRS)
    assert _tags(run_dir) == {f"task-old-{i:02d}" for i in range(12 - H.RUN_STDIO_RETAIN_PAIRS, 12)}
    assert open(lock_path, "rb").read() == b"1234"
    assert open(claim_path, "rb").read() == b"{}"
    assert open(notes_path, "rb").read() == b"keep me"


def test_prune_handles_lone_files_and_missing_dir(tmp_path):
    missing = str(tmp_path / "no-such-run")
    assert H._prune_run_stdio(missing) == 0

    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    base = time.time() - 1000.0
    # A lone .out survives a failed .err open in _spawn_contained; it still
    # counts as a group and is pruned like any other pair.
    lone = os.path.join(run_dir, "task-lone.out")
    with open(lone, "wb") as fh:
        fh.write(b"")
    os.utime(lone, (base, base))
    for i in range(H.RUN_STDIO_RETAIN_PAIRS):
        _seed_pair(run_dir, f"keep-{i:02d}", base + 10 + i)

    pruned = H._prune_run_stdio(run_dir)

    assert pruned == 1
    assert not os.path.exists(lone)
    assert len(_tags(run_dir)) == H.RUN_STDIO_RETAIN_PAIRS


def test_prune_is_noop_at_or_below_retention(tmp_path):
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    base = time.time() - 1000.0
    for i in range(H.RUN_STDIO_RETAIN_PAIRS):
        _seed_pair(run_dir, f"run-{i:02d}", base + i)

    assert H._prune_run_stdio(run_dir) == 0
    assert len(_tags(run_dir)) == H.RUN_STDIO_RETAIN_PAIRS


def test_run_once_prunes_old_stdio_and_keeps_current(tmp_path):
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    base = time.time() - 1000.0
    for i in range(10):
        _seed_pair(run_dir, f"old-{i:02d}", base + i)

    host = make_host(tmp_path)
    spec = make_spec(tmp_path, dispatch="d-current", argv=[PY, "-c", "print('hello-stdio')"])
    result = host.run_once(spec)

    assert result.outcome == Outcome.COMPLETED
    assert host.busy is False
    current_out = os.path.join(run_dir, "task-d-current.out")
    with open(current_out, "rb") as fh:
        assert b"hello-stdio" in fh.read()
    # Prune-before-spawn keeps the 8 newest old pairs; the current run then
    # adds its own pair, so the steady state is bounded at RETAIN + 1.
    assert len(_tags(run_dir)) <= H.RUN_STDIO_RETAIN_PAIRS + 1
    assert "task-d-current" in _tags(run_dir)
    assert "task-old-00" not in _tags(run_dir)
    assert "task-old-01" not in _tags(run_dir)
