"""Cannon motor acceptance: deterministic T1-T13 proof matrix.

FAIL = fix scripts/cannon_motor.py, never weaken these expectations.
Each test uses an isolated tmp state dir; no network, no provider.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.cannon_motor import CannonMotor

WQ = Path("scripts/work_queue.py")


def wq(state_dir, *argv):
    out = subprocess.check_output(
        [sys.executable, str(WQ), "--state-dir", str(state_dir), *argv],
        text=True)
    return json.loads(out)


def seed(state_dir, n, package="pk"):
    wq(state_dir, "init", package)
    for i in range(1, n + 1):
        wq(state_dir, "add", json.dumps({
            "task_id": f"t{i}", "package_id": package,
            "description": f"task {i}", "dependencies": [],
            "read_scopes": [], "write_scopes": [f"scope-{i}"],
            "status": "READY", "priority": i}))


def statuses(state_dir):
    return {t: v["status"]
            for t, v in wq(state_dir, "state")["tasks"].items()}


def test_t1_five_tasks_serial(tmp_path):
    seed(tmp_path, 5)
    motor = CannonMotor(tmp_path)
    assert motor.start(cooldown=0)["started"] is True
    motor.run()
    inv = motor.invariants()
    assert inv["DONE"] == 5
    assert inv["DUPLICATE_EXECUTIONS"] == 0
    assert inv["LOST_RESULTS"] == 0
    assert inv["MAX_ACTIVE"] == 1
    assert inv["HUMAN_CONTINUE"] == 0


def test_t2_ten_tasks_serial(tmp_path):
    seed(tmp_path, 10)
    motor = CannonMotor(tmp_path)
    motor.start(cooldown=0)
    motor.run()
    inv = motor.invariants()
    assert inv["DONE"] == 10
    assert inv["DUPLICATE_EXECUTIONS"] == 0
    assert inv["LOST_RESULTS"] == 0
    assert inv["MAX_ACTIVE"] == 1


def test_t3_pause_during_task2(tmp_path):
    seed(tmp_path, 4)
    motor = CannonMotor(
        tmp_path,
        hooks={"on_task_start": lambda m, tid:
               m.request_pause() if tid == "t2" else None})
    motor.start(cooldown=0)
    motor.run()
    assert motor.state == "PAUSED"
    st = statuses(tmp_path)
    assert st["t2"] == "DONE" and st["t3"] == "READY"


def test_t4_resume_completes_without_rerun(tmp_path):
    seed(tmp_path, 4)
    motor = CannonMotor(
        tmp_path,
        hooks={"on_task_start": lambda m, tid:
               m.request_pause() if tid == "t2" else None})
    motor.start(cooldown=0)
    motor.run()
    assert motor.state == "PAUSED"
    assert motor.request_resume()["resumed"] is True
    motor.run()
    inv = motor.invariants()
    assert inv["DONE"] == 4
    assert inv["DUPLICATE_EXECUTIONS"] == 0
    assert all(c == 1 for c in motor.m["executions"].values())


def test_t5_stop_after_current(tmp_path):
    seed(tmp_path, 4)
    motor = CannonMotor(
        tmp_path,
        hooks={"on_task_start": lambda m, tid:
               m.request_stop() if tid == "t2" else None})
    motor.start(cooldown=0)
    motor.run()
    assert motor.state in ("IDLE", "COMPLETED")
    assert motor.state != "PAUSED"
    st = statuses(tmp_path)
    assert st["t2"] == "DONE" and st["t3"] == "READY"


def test_t6_reload_during_running(tmp_path):
    seed(tmp_path, 3)
    seen = {}

    def hook(m, tid):
        if tid == "t1":
            other = CannonMotor(tmp_path)
            seen["state"] = other.state
            seen["current"] = other.m["current_task"]

    motor = CannonMotor(tmp_path, hooks={"on_task_start": hook})
    motor.start(cooldown=0)
    motor.run()
    assert seen == {"state": "RUNNING", "current": "t1"}
    assert motor.invariants()["DONE"] == 3


def test_t7_reload_during_paused(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(
        tmp_path,
        hooks={"on_task_start": lambda m, tid:
               m.request_pause() if tid == "t1" else None})
    motor.start(cooldown=0)
    motor.run()
    other = CannonMotor(tmp_path)
    assert other.state == "PAUSED"
    assert other.request_resume()["resumed"] is True
    other.run()
    assert other.invariants()["DONE"] == 3


def test_t8_double_start_single_run(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(tmp_path)
    first = motor.start(cooldown=0)
    second = motor.start(cooldown=0)
    assert first["started"] is True
    assert second == {"started": False, "reason": "already_running",
                      "run_id": first["run_id"]}
    motor.run()
    assert motor.invariants()["DONE"] == 3
    assert motor.invariants()["DUPLICATE_EXECUTIONS"] == 0


def test_t9_double_pause_idempotent(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(
        tmp_path,
        hooks={"on_task_start": lambda m, tid:
               m.request_pause() if tid == "t1" else None})
    motor.start(cooldown=0)
    motor.run()
    assert motor.request_pause()["reason"] == "already_paused"
    assert motor.state == "PAUSED"


def test_t10_double_resume_no_duplicate(tmp_path):
    seed(tmp_path, 2)
    motor = CannonMotor(
        tmp_path,
        hooks={"on_task_start": lambda m, tid:
               m.request_pause() if tid == "t1" else None})
    motor.start(cooldown=0)
    motor.run()
    assert motor.request_resume()["resumed"] is True
    assert motor.request_resume()["reason"] == "already_running"
    motor.run()
    inv = motor.invariants()
    assert inv["DONE"] == 2 and inv["DUPLICATE_EXECUTIONS"] == 0


def test_t11_double_stop_single_request(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(tmp_path)
    motor.start(cooldown=0)
    assert motor.request_stop()["stopped"] is True
    assert motor.request_stop()["reason"] == "already_requested"
    motor.run()
    assert motor.state in ("IDLE", "COMPLETED")


def test_t12_unknown_result_halts_chain(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(tmp_path, behaviors={"t2": "unknown"})
    motor.start(cooldown=0)
    motor.run()
    assert motor.state in ("ERROR", "BLOCKED")
    st = statuses(tmp_path)
    assert st["t1"] == "DONE"
    assert st["t2"] == "BLOCKED"
    assert st["t3"] == "READY"
    assert motor.m["needs_review"] == ["t2"]
    assert motor.invariants()["LOST_RESULTS"] == 0


def test_t13_reopen_done_stays_done(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(tmp_path)
    motor.start(cooldown=0)
    motor.run()
    before = dict(motor.m["executions"])
    reopened = CannonMotor(tmp_path)
    assert reopened.start(cooldown=0)["started"] is True
    reopened.run()
    assert reopened.m["executions"] == before
    assert reopened.invariants()["DONE"] == 3

def test_t14_infinite_mode_idles(tmp_path):
    seed(tmp_path, 2)
    m = CannonMotor(tmp_path, behaviors={})
    m.start(mode="INFINITE", cooldown=0.0)
    res = m.run(max_steps=5)
    assert m.state == "IDLE"
    assert m.m["done_count"] == 2
