"""Regression: crash/resume auto-blocks the interrupted task for review.

CannonMotor persists current_task while a task executes. If the process
dies there, the next run_step must NOT blindly re-execute: when the queue
record is not DONE/VERIFYING the task is blocked with CRASH_DURING_EXECUTION,
queued in needs_review, and the motor goes BLOCKED (canonical review-before-
resume). When the queue record already shows DONE/VERIFYING, the stale
current_task is cleared and the step continues without blocking.

Isolated tmp state dirs; persisted-state crash simulation; no network.
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
        "status": "READY"}))


def crash_mid_task(state_dir):
    """Persist exactly what a crash between admit and finish leaves behind."""
    motor = CannonMotor(state_dir)
    assert motor.start(cooldown=0)["started"] is True
    motor.m["current_task"] = "t1"
    motor._save()


def test_crash_mid_task_auto_blocks_for_review(tmp_path):
    seed(tmp_path)
    crash_mid_task(tmp_path)
    resumed = CannonMotor(tmp_path)
    report = resumed.run_step()
    assert report["step"] == "crash_recovery"
    assert report["task"] == "t1"
    assert resumed.state == "BLOCKED"
    assert resumed.m["needs_review"] == ["t1"]
    assert resumed.m["current_task"] is None
    assert resumed.m["error"] == "crash_recovery_blocked:t1"
    # Never re-executed, never marked done, nothing lost.
    assert resumed.invariants()["DONE"] == 0
    assert resumed.invariants()["LOST_RESULTS"] == 0


def test_crash_with_done_record_clears_without_blocking(tmp_path):
    seed(tmp_path)
    wq(tmp_path, "claim", "--worker", "w1")
    wq(tmp_path, "complete", "t1", "--result-json", "{}",
       "--stage", "ACCEPTED")
    crash_mid_task(tmp_path)
    resumed = CannonMotor(tmp_path)
    report = resumed.run_step()
    assert report["step"] != "crash_recovery"
    assert resumed.state != "BLOCKED"
    assert resumed.m["needs_review"] == []
    assert resumed.m["current_task"] is None
