"""Regression: run_step fails closed when the queue record vanishes mid-step.

CannonMotor.run_step claims a task, then re-reads its full record from
queue.json for the local-executor path. If the record disappears in between
(concurrent admin/prune, crash-restore GC), the direct ['tasks'][task_id]
lookup raised an uncaught KeyError that escaped run()/supervise() instead
of failing closed to BLOCKED + needs_review like every other unreadable-
backend case in this file.

Isolated tmp state dirs; hook-driven TOCTOU; no network, no provider.
"""
import json
import subprocess
import sys
from pathlib import Path

import scripts.cannon_motor as cannon_motor
from scripts.cannon_motor import CannonMotor

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


def drop_record(state_dir, task_id="t1"):
    """Remove the task record from backend truth (TOCTOU simulation)."""
    raw_path = Path(state_dir) / "queue.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    del raw["tasks"][task_id]
    raw_path.write_text(json.dumps(raw), encoding="utf-8")


def test_run_step_missing_record_fails_closed(tmp_path):
    seed(tmp_path)

    def _vanish(motor, task_id):
        drop_record(motor.state_dir, task_id)

    motor = CannonMotor(tmp_path, hooks={"on_task_start": _vanish})
    assert motor.start(cooldown=0)["started"] is True
    # Must not raise: fail closed to BLOCKED with the task queued for review.
    report = motor.run_step()
    assert motor.state == "BLOCKED"
    assert "t1" in motor.m["needs_review"]
    assert motor.m["current_task"] is None
    assert report["step"] == "error"


def test_run_step_missing_record_never_marks_done(tmp_path):
    seed(tmp_path)
    motor = CannonMotor(
        tmp_path, hooks={"on_task_start": lambda m, tid: drop_record(m.state_dir, tid)})
    assert motor.start(cooldown=0)["started"] is True
    motor.run_step()
    assert motor.invariants()["DONE"] == 0
    assert motor.invariants()["LOST_RESULTS"] == 0
