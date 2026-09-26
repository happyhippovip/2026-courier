"""Regression: mac_worker_adapter transport is repo-root anchored (G).

A foreign caller cwd previously scattered inbox/outbox and the
delivered result outside the repo (lost-result risk). These pin:
delivery lands under the root from any cwd, the default root is the
file-anchored repo root, and the timeout path records there too.
"""
import json
from pathlib import Path

import pytest

from scripts import mac_worker_adapter as adapter


@pytest.fixture
def root(tmp_path):
    box = tmp_path / "root"
    (box / "scripts" / "mac_worker" / "outbox").mkdir(parents=True)
    return box


def write_task(root: Path, task_id="T-1"):
    task_file = root / f"{task_id}.json"
    task_file.write_text(json.dumps(
        {"task_id": task_id, "goal_id": "g", "instruction": "i"}),
        encoding="utf-8")
    return task_file


def test_delivery_lands_under_root_from_foreign_cwd(root, tmp_path, monkeypatch):
    foreign = tmp_path / "foreign-cwd"
    foreign.mkdir()
    monkeypatch.chdir(foreign)
    (root / "scripts" / "mac_worker" / "outbox" / "T-1_result.json").write_text(
        '{"status":"SUCCESS"}', encoding="utf-8")
    posted = []
    monkeypatch.setattr(adapter, "post_result", lambda res: posted.append(res))
    adapter.run(str(write_task(root)), root=root)
    assert (root / "scripts" / "mac_worker" / "inbox" / "T-1.json").exists()
    assert posted[-1]["status"] == "SUCCESS"
    assert not (foreign / "scripts").exists()
    assert not (foreign / "results").exists()


def test_timeout_records_failure_under_root(root, tmp_path, monkeypatch):
    foreign = tmp_path / "foreign-cwd"
    foreign.mkdir()
    monkeypatch.chdir(foreign)
    calls = iter([0.0, 400.0])
    monkeypatch.setattr(adapter.time, "time", lambda: next(calls))
    monkeypatch.setattr(adapter.time, "sleep", lambda s: None)
    posted = []
    monkeypatch.setattr(adapter, "post_result", lambda res: posted.append(res))
    posted = []
    monkeypatch.setattr(adapter, "post_result", lambda res: posted.append(res))
    adapter.run(str(write_task(root)), root=root)
    recorded = posted[0]
    assert recorded["status"] == "FAILED" and recorded["reason"] == "TIMEOUT"
    assert not (foreign / "results").exists()


def test_default_root_is_file_anchored():
    assert adapter.REPO_ROOT == Path(adapter.__file__).resolve().parents[1]
    src = Path(adapter.__file__).read_text(encoding="utf-8")
    assert 'Path("scripts' not in src
    assert '"results/incoming"' not in src


def test_timeout_preserves_canonical_identity(root, monkeypatch):
    task_file = root / "T-id.json"
    task_file.write_text(json.dumps({
        "task_id": "T-id",
        "goal_id": "g-1",
        "attempt_id": "attempt-1",
        "dispatch_id": "dispatch-1",
        "worker_id": "MAC-01",
    }), encoding="utf-8")
    calls = iter([0.0, 400.0])
    monkeypatch.setattr(adapter.time, "time", lambda: next(calls))
    monkeypatch.setattr(adapter.time, "sleep", lambda s: None)
    posted = []
    monkeypatch.setattr(adapter, "post_result", lambda res: posted.append(res))
    adapter.run(str(task_file), root=root)
    recorded = posted[0]
    assert recorded["goal_id"] == "g-1"
    assert recorded["task_id"] == "T-id"
    assert recorded["attempt_id"] == "attempt-1"
    assert recorded["dispatch_id"] == "dispatch-1"
    assert recorded["worker_id"] == "MAC-01"
    assert recorded["result_id"] == "result-dispatch-1-timeout"
    assert recorded["status"] == "FAILED"

