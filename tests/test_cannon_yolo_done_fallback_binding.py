"""Regression: YOLO done-path fallback result binding (contract gap).

The done path in scripts/cannon_motor.py uses the executor commit SHA as
result_id when present (pinned by test_m5_yolo_done_writes_result_artifact_
with_commit_sha). When the executor returns done WITHOUT a commit, the
motor must fall back to the canonical (task_id, attempt_id, dispatch_id,
executor_kind=YOLO) binding: "result-"-prefixed, retry-distinct, and
coherent between artifact and queue record. No committed test covers this
branch end-to-end; this file pins it.

Isolated tmp state dirs; stubbed YOLO executor; no network, no provider.
"""
import json
import subprocess
import sys
from pathlib import Path

import scripts.cannon_motor as cannon_motor
from scripts.cannon_motor import CannonMotor, yolo_fallback_result_id

WQ = Path(cannon_motor.__file__).resolve().parent / "work_queue.py"


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


class StubYoloNoCommit:
    """Executor returning done with no commit: forces the fallback branch."""

    def __init__(self):
        self.ended = []

    def gate(self):
        return ""

    def execute(self, tid):
        return ("done", "", {"Aufgabe": tid, "Status": "ERLEDIGT"})

    def end(self, reason):
        self.ended.append(reason)


def queue_record(state_dir, task_id="t1"):
    raw = json.loads((Path(state_dir) / "queue.json").read_text(
        encoding="utf-8"))
    return raw["tasks"][task_id]


def test_done_without_commit_binds_canonical(tmp_path):
    seed(tmp_path)
    motor = CannonMotor(tmp_path)
    motor.yolo = StubYoloNoCommit()
    assert motor.start(cooldown=0)["started"] is True
    report = motor.run_step()
    assert report["step"] == "done"

    record = queue_record(tmp_path)
    assert record["status"] == "DONE"
    artifact = json.loads(
        (motor.results_dir / "t1.result.json").read_text(encoding="utf-8"))
    expected = yolo_fallback_result_id("t1", record)
    assert expected.startswith("result-")
    assert artifact["result_id"] == expected
    assert artifact["task_id"] == "t1"
    assert artifact["outcome"] == "ok"
    # Queue record and artifact agree on the bound identity.
    assert record["result_id"] == expected
    assert record["result"]["result_id"] == expected
    assert motor.invariants()["LOST_RESULTS"] == 0


def test_done_without_commit_retry_distinct(tmp_path):
    seed(tmp_path)
    motor = CannonMotor(tmp_path)
    motor.yolo = StubYoloNoCommit()
    assert motor.start(cooldown=0)["started"] is True
    assert motor.run_step()["step"] == "done"
    first = json.loads(
        (motor.results_dir / "t1.result.json").read_text(encoding="utf-8")
    )["result_id"]

    # Simulate a retry: the same task returns READY, so the next claim
    # mints a fresh (attempt_id, dispatch_id) pair.
    raw_path = Path(tmp_path) / "queue.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    assert raw["tasks"]["t1"]["attempt_id"] == "t1:attempt:1"
    raw["tasks"]["t1"]["status"] = "READY"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    assert motor.run_step()["step"] == "done"
    record = queue_record(tmp_path)
    assert record["attempt_id"] == "t1:attempt:2"
    assert record["dispatch_id"] == "t1:dispatch:2"
    second = json.loads(
        (motor.results_dir / "t1.result.json").read_text(encoding="utf-8")
    )["result_id"]
    assert second.startswith("result-")
    assert second != first
    assert second == yolo_fallback_result_id("t1", record)
    assert record["result_id"] == second
    assert motor.invariants()["DONE"] == 1
    assert motor.invariants()["LOST_RESULTS"] == 0
