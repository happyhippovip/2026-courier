"""Overnight Dauerlauf acceptance: finite/infinite, counters, restart, prompt guard.

FAIL = fix scripts/cannon_motor.py, never weaken these expectations.
Local fake worker only. LIVE_MUSE stays UNPROVEN.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from scripts.cannon_motor import CannonMotor
from scripts.mac_adapter import MacAdapter

WQ = Path("scripts/work_queue.py")


def wq(state_dir, *argv):
    out = subprocess.check_output(
        [sys.executable, str(WQ), "--state-dir", str(state_dir), *argv],
        text=True)
    return json.loads(out)


def seed(state_dir, n, package="night", prompt_id=None, descriptions=None):
    wq(state_dir, "init", package)
    for i in range(1, n + 1):
        task = {"task_id": f"t{i}", "package_id": package,
                "description": (descriptions[i - 1]
                                if descriptions else f"night task {i}"),
                "dependencies": [], "read_scopes": [],
                "write_scopes": [f"night-scope-{i}"],
                "status": "READY", "priority": i}
        if prompt_id:
            task["prompt_id"] = prompt_id
        wq(state_dir, "add", json.dumps(task))


def test_finite_10_full_contract(tmp_path):
    seed(tmp_path, 10)
    motor = CannonMotor(tmp_path)
    assert motor.start(mode="FINITE", limit=10, cooldown=0)["started"]
    motor.run()
    inv = motor.invariants()
    assert inv["DONE"] == 10
    assert inv["REMAINING"] == 0
    assert inv["STARTED"] == 10
    assert inv["MAX_ACTIVE"] == 1
    assert inv["DUPLICATE_EXECUTIONS"] == 0
    assert inv["LOST_RESULTS"] == 0
    assert inv["HUMAN_CONTINUE"] == 0


def test_finite_100_counter_monotonic(tmp_path):
    seed(tmp_path, 100, package="p100")
    seen = []
    motor = CannonMotor(tmp_path)
    orig_step = motor.run_step

    def traced():
        rep = orig_step()
        if rep["step"] == "done":
            seen.append(motor.remaining())
        return rep

    motor.run_step = traced
    motor.start(mode="FINITE", limit=100, cooldown=0)
    motor.run()
    assert motor.invariants()["DONE"] == 100
    assert seen == sorted(seen, reverse=True)
    assert seen[-1] == 0


def test_infinite_drains_then_waits(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(tmp_path)
    motor.start(mode="INFINITE", cooldown=0)
    motor.run()
    assert motor.state == "IDLE"
    assert motor.m["waiting_for_work"] is True
    assert motor.invariants()["DONE"] == 3
    assert len(wq(tmp_path, "state")["tasks"]) == 3  # nothing fabricated


def test_counters_survive_pause_resume_stop(tmp_path):
    seed(tmp_path, 4)
    motor = CannonMotor(
        tmp_path,
        hooks={"on_task_start": lambda m, tid:
               m.request_pause() if tid == "t2" else None})
    motor.start(mode="FINITE", limit=10, cooldown=0)
    motor.run()
    assert motor.state == "PAUSED"
    assert (motor.m["started_count"], motor.m["done_count"]) == (2, 2)
    motor.request_resume()
    motor.run()
    assert motor.invariants()["DONE"] == 4
    assert motor.m["started_count"] == 4


def test_restart_reopen_counters_intact(tmp_path):
    seed(tmp_path, 4)
    motor = CannonMotor(tmp_path)
    motor.start(mode="FINITE", limit=10, cooldown=0)
    motor.run_step()
    motor.request_pause()
    motor.run_step()  # finishes current, then PAUSED
    assert motor.state == "PAUSED"
    reopened = CannonMotor(tmp_path)  # simulate app restart
    assert reopened.m["started_count"] == 2
    assert reopened.m["done_count"] == 2
    assert reopened.state == "PAUSED"
    reopened.request_resume()
    reopened.run()
    assert reopened.invariants()["DONE"] == 4
    assert reopened.invariants()["DUPLICATE_EXECUTIONS"] == 0


def test_unknown_halts_with_counters(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(tmp_path, behaviors={"t2": "unknown"})
    motor.start(mode="FINITE", limit=10, cooldown=0)
    motor.run()
    assert motor.state in ("ERROR", "BLOCKED")
    assert motor.m["started_count"] == 2
    assert motor.m["done_count"] == 1
    assert motor.remaining() == 8


def test_million_limit_without_preload(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(tmp_path)
    motor.start(mode="FINITE", limit=1000000, cooldown=0)
    motor.run()
    assert motor.m["started_count"] == 3
    assert motor.remaining() == 999997
    assert len(wq(tmp_path, "state")["tasks"]) == 3


def test_mutating_prompt_duplicate_blocked(tmp_path):
    motor = CannonMotor(tmp_path)
    assert motor.save_prompt("P1", "delete X", "mutating")["saved"]
    seed(tmp_path, 3, prompt_id="P1",
         descriptions=["same input", "same input", "other input"])
    motor.start(mode="FINITE", cooldown=0)
    motor.run()
    st = {t: v["status"] for t, v in wq(tmp_path, "state")["tasks"].items()}
    assert st["t1"] == "DONE"
    assert st["t2"] == "BLOCKED"
    assert st["t3"] == "DONE"


def test_readonly_prompt_may_repeat(tmp_path):
    motor = CannonMotor(tmp_path)
    motor.save_prompt("P2", "read status", "readonly")
    seed(tmp_path, 2, prompt_id="P2",
         descriptions=["same input", "same input"])
    motor.start(mode="FINITE", cooldown=0)
    motor.run()
    assert motor.invariants()["DONE"] == 2


def test_cooldown_waits_after_completion(tmp_path):
    seed(tmp_path, 2)
    motor = CannonMotor(tmp_path)
    motor.start(mode="FINITE", cooldown=0.2)
    t0 = time.monotonic()
    motor.run()
    assert time.monotonic() - t0 >= 0.4
    assert motor.invariants()["DONE"] == 2


def test_adapter_dauerlauf_finite_snapshot(tmp_path):
    adapter = MacAdapter(tmp_path)
    adapter.seed(5)
    out = adapter.dauerlauf(art="begrenzt", limit=5, cooldown=0)
    snap = out["snapshot"]
    assert snap["state"] == "COMPLETED"
    assert snap["overnight"]["laufart"] == "BEGRENZT"
    assert snap["overnight"]["gestartet"] == 5
    assert snap["overnight"]["erledigt"] == 5
    assert snap["overnight"]["verbleibend"] == 0
    assert snap["overnight"]["modus"] == "NORMAL"
    assert snap["overnight"]["gleichzeitig"] == 1
    assert snap["overnight"]["letztes_ergebnis"]["task"] == "t5"


def test_adapter_dauerlauf_infinite_waits(tmp_path):
    adapter = MacAdapter(tmp_path)
    adapter.seed(2)
    motor = CannonMotor(tmp_path)
    motor.start(mode="INFINITE", cooldown=0)
    result = motor.supervise(max_cycles=6, idle_sleep=0.01)
    assert result["state"] == "IDLE"
    snap = MacAdapter(tmp_path).status()
    assert snap["overnight"]["laufart"] == "UNENDLICH"
    assert snap["overnight"]["verbleibend"] == "∞"
    assert snap["overnight"]["erledigt"] == 2
