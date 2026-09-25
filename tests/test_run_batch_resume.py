"""Regression: run_batch crash/resume accounting and save durability.

Covers T4: a resumed IN_PROGRESS/WAITING_PROVIDER item used to re-execute
under the same attempt_id (duplicate execution, indistinguishable retries),
and save_batch never fsynced the parent directory (completed saves could
vanish on crash despite an fsynced file).
"""
import json
import os
import stat

import scripts.run_batch as rb


def _write_batch(path, status, attempt, sequence=5, simulated=False):
    item = {
        "sequence": sequence,
        "description": "probe",
        "status": status,
        "attempt_id": attempt,
        "prompt_id": "p-1",
        "goal_id": "g-1",
        "depends_on": None,
    }
    if simulated:
        item["quota_hit_simulated"] = True
    path.write_text(json.dumps({"items": [item]}))


def _read_item(path):
    return json.loads(path.read_text())["items"][0]


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(rb, "QUEUE_DIR", tmp_path)
    monkeypatch.setattr(rb.time, "sleep", lambda s: None)
    monkeypatch.setattr(rb, "get_git_sha", lambda: "a" * 40)


def test_fresh_run_counts_first_attempt(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_batch(tmp_path / "b.json", "QUEUED", 0)
    rb.run_batch("b")
    item = _read_item(tmp_path / "b.json")
    assert item["status"] == "COMPLETED"
    assert item["attempt_id"] == 1
    assert set(item["evidence"]) >= {"commit_sha", "result_id"}


def test_resume_counts_new_attempt(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    # Leftover of a crash after QUEUED->IN_PROGRESS was persisted.
    _write_batch(tmp_path / "b.json", "IN_PROGRESS", 1)
    rb.run_batch("b")
    item = _read_item(tmp_path / "b.json")
    assert item["status"] == "COMPLETED"
    assert item["attempt_id"] == 2


def test_quota_simulation_not_repeated_on_resume(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    # Crash inside the quota-hit window: flag already set, attempt 1.
    _write_batch(tmp_path / "b.json", "WAITING_PROVIDER", 1,
                 sequence=9, simulated=True)
    rb.run_batch("b")
    item = _read_item(tmp_path / "b.json")
    assert item["status"] == "COMPLETED"
    assert item["attempt_id"] == 2
    assert item["quota_hit_simulated"] is True


def test_save_batch_fsyncs_parent_directory(monkeypatch, tmp_path):
    fsynced_dirs = []
    real_fsync = os.fsync

    def _recorder(fd):
        try:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                fsynced_dirs.append(fd)
        finally:
            return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", _recorder)
    target = tmp_path / "batch.json"
    rb.save_batch(target, {"items": []})
    assert json.loads(target.read_text()) == {"items": []}
    assert len(fsynced_dirs) == 1
