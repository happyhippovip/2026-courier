"""Regression: work_queue rejects a second complete (Duplicate Execution).

cmd_complete only accepts CLAIMED/RUNNING tasks. Completing a DONE task
again — with the same or a different result — must return "not claimed"
and must NOT overwrite the recorded result. No committed test pins this
at the queue layer; this file does.

Isolated tmp state dirs; work_queue CLI via subprocess; no network.
"""
import json
import subprocess
import sys
from pathlib import Path

import scripts.work_queue as work_queue_module

WQ = Path(work_queue_module.__file__).resolve()


def wq(state_dir, *argv):
    out = subprocess.check_output(
        [sys.executable, str(WQ), "--state-dir", str(state_dir), *argv],
        text=True)
    return json.loads(out)


def seed(state_dir):
    wq(state_dir, "init", "pk")
    wq(state_dir, "add", json.dumps({
        "task_id": "t1", "package_id": "pk", "description": "task 1",
        "dependencies": [], "read_scopes": [], "write_scopes": ["scope-1"],
        "status": "READY", "priority": 1}))


def complete(state_dir, result_id, stage="ACCEPTED"):
    return wq(state_dir, "complete", "t1",
              "--result-json", json.dumps({"result_id": result_id}),
              "--stage", stage)


def record(state_dir):
    # Backend truth: the state CLI deliberately projects only
    # status/stage, so read queue.json for the recorded identity.
    raw = json.loads((Path(state_dir) / "queue.json").read_text(
        encoding="utf-8"))
    return raw["tasks"]["t1"]


def test_second_complete_same_result_rejected(tmp_path):
    seed(tmp_path)
    assert wq(tmp_path, "claim", "--worker", "w1")["claimed"] == "t1"
    out = complete(tmp_path, "result-first")
    assert out["done"] == "t1" and out["stage"] == "ACCEPTED"

    again = complete(tmp_path, "result-first")
    assert again.get("error") == "not claimed"
    rec = record(tmp_path)
    assert rec["status"] == "DONE"
    assert rec["result_id"] == "result-first"
    assert rec["result"]["result_id"] == "result-first"


def test_second_complete_different_result_does_not_overwrite(tmp_path):
    seed(tmp_path)
    assert wq(tmp_path, "claim", "--worker", "w1")["claimed"] == "t1"
    assert complete(tmp_path, "result-first")["done"] == "t1"

    other = complete(tmp_path, "result-evil")
    assert other.get("error") == "not claimed"
    rec = record(tmp_path)
    assert rec["status"] == "DONE"
    assert rec["result_id"] == "result-first"
    assert rec["result"]["result_id"] == "result-first"


def test_complete_unknown_task_rejected(tmp_path):
    seed(tmp_path)
    out = wq(tmp_path, "complete", "nope",
             "--result-json", json.dumps({"result_id": "result-x"}),
             "--stage", "ACCEPTED")
    assert out.get("error") == "not claimed"
