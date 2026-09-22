"""Bounded local fake proof. No provider calls or live state mutation."""
import io
import json
from unittest.mock import Mock

import pytest

from app.cannon import web
from scripts import cannon_motor
from scripts.cannon_motor import CannonMotor
from scripts.mac_adapter import MacAdapter


@pytest.mark.parametrize("mode", ["BEGRENZT", "UNENDLICH"])
def test_web_million_is_limit_not_seed(monkeypatch, mode):
    child = Mock(stdin=io.BytesIO(), stderr=io.BytesIO())
    child.poll.return_value = None
    launch = Mock(return_value=(child, Mock(), {}))
    external = Mock(side_effect=AssertionError("START must not seed"))
    monkeypatch.setattr(web, "CHILD", None)
    monkeypatch.setattr(web, "JOB", None)
    monkeypatch.setattr(web, "launch_gated", launch)
    monkeypatch.setattr(web.subprocess, "check_call", external)
    assert web.action({"action": "START", "mode": mode, "count": 1000000})["ok"]
    command = launch.call_args.args[0]
    assert "seed" not in command
    assert launch.call_count == 1


@pytest.mark.parametrize("mode, limit", [("FINITE", 1000000), ("INFINITE", None)])
def test_only_one_lazy_admission(mode, limit, tmp_path):
    motor = CannonMotor(tmp_path)
    motor.start(mode=mode, limit=1000000, cooldown=0, local_fake=True)
    assert motor.m["start_limit"] == limit
    assert len(motor.queue_snapshot()["tasks"]) == 0
    motor.run_step()
    assert len(motor.queue_snapshot()["tasks"]) == 1
    assert motor.invariants()["MAX_ACTIVE"] == 1
    assert motor.m["done_count"] == 1


def test_infinite_empty_waits_without_polling(tmp_path, monkeypatch):
    motor = CannonMotor(tmp_path)
    motor.start(mode="INFINITE", limit=1000000)
    step = Mock(wraps=motor.run_step)
    monkeypatch.setattr(motor, "run_step", step)
    monkeypatch.setattr(cannon_motor.time, "sleep", Mock(side_effect=AssertionError("No idle polling")))
    result = motor.supervise(max_cycles=1000000)
    assert step.call_count == 1
    assert result["state"] == "IDLE"
    assert motor.m["waiting_for_work"] and motor.m["start_limit"] is None
    assert motor.queue_snapshot()["tasks"] == {}
    assert MacAdapter(tmp_path).status()["waiting_for_work"]


def test_second_admission_after_durable_reconcile_and_five_seconds(tmp_path, monkeypatch):
    now = [1000.0]
    sleeps = []
    motor = CannonMotor(tmp_path)
    monkeypatch.setattr(cannon_motor.time, "time", lambda: now[0])

    def sleep(seconds):
        snap = motor.queue_snapshot()
        persisted = json.loads(motor.motor_file.read_text())
        assert len(snap["tasks"]) == len(sleeps) + 1
        assert all(task["status"] == "DONE" for task in snap["tasks"].values())
        last = persisted["last_result"]
        receipt = json.loads((motor.results_dir / (last["task"] + ".result.json")).read_text())
        assert receipt["result_id"] == last["result_id"]
        assert seconds == 5
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(cannon_motor.time, "sleep", sleep)
    motor.start(mode="FINITE", limit=2, local_fake=True)
    motor.supervise(max_cycles=4)
    assert sleeps == [5, 5]
    assert motor.state == "COMPLETED" and motor.remaining() == 0
    assert len(motor.queue_snapshot()["tasks"]) == 2  # no third admission
    assert motor.invariants()["DUPLICATE_EXECUTIONS"] == 0


def test_unknown_never_admits_second_task_or_restarts(tmp_path):
    def inject(motor, task_id):
        motor.behaviors[task_id] = "unknown"
    motor = CannonMotor(tmp_path, hooks={"on_task_start": inject})
    motor.start(mode="INFINITE", local_fake=True, cooldown=0)
    motor.supervise(max_cycles=10)
    assert motor.state in ("ERROR", "BLOCKED")
    assert (motor.m["started_count"], motor.m["done_count"]) == (1, 0)
    assert len(motor.queue_snapshot()["tasks"]) == 1
    assert CannonMotor(tmp_path).start(mode="INFINITE", local_fake=True)["reason"] == "review_required"


def test_missing_artifact_cannot_admit_next(tmp_path):
    motor = CannonMotor(tmp_path)
    motor.start(mode="FINITE", limit=1000000, local_fake=True, cooldown=0)
    motor.run_step()
    task_id = motor.m["last_result"]["task"]
    (motor.results_dir / (task_id + ".result.json")).unlink()
    assert motor.run_step()["step"] == "error"
    assert len(motor.queue_snapshot()["tasks"]) == 1


def test_seed_large_count_rejected_before_queue_write(tmp_path):
    adapter = MacAdapter(tmp_path)
    with pytest.raises(ValueError, match="small explicit demo"):
        adapter.seed(1000000)
    assert not (tmp_path / "queue.json").exists()


def test_adapter_supervisor_lock_rejects_duplicate(tmp_path):
    import fcntl
    adapter = MacAdapter(tmp_path)
    with (tmp_path / "supervisor.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = adapter.dauerlauf(limit=1000000, local_fake=True, max_cycles=1)
    assert result == {"started": False, "reason": "supervisor_active"}
    assert not (tmp_path / "queue.json").exists()


def test_adapter_cli_path_persists_limit_without_preload(tmp_path):
    adapter = MacAdapter(tmp_path)
    result = adapter.dauerlauf(limit=1000000, local_fake=True, cooldown=0, max_cycles=1)
    assert result["snapshot"]["invariants"]["MAX_ACTIVE"] == 1
    assert sum(result["snapshot"]["task_counts"].values()) == 1
    assert CannonMotor(tmp_path).m["start_limit"] == 1000000


def test_stop_request_is_scoped_to_each_new_run(tmp_path):
    motor = CannonMotor(tmp_path)
    motor.start(mode="FINITE", limit=1000000, cooldown=0)
    assert motor.request_stop()["stopped"] is True
    motor.run_step()  # empty first local run terminates
    motor.start(mode="INFINITE", cooldown=0)
    assert motor.request_stop()["stopped"] is True


def test_reopen_during_cooldown_preserves_single_frontier(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(cannon_motor.time, "time", lambda: now[0])
    motor = CannonMotor(tmp_path)
    motor.start(mode="FINITE", limit=2, local_fake=True)

    def interrupt_sleep(seconds):
        raise InterruptedError("test restart during cooldown")

    monkeypatch.setattr(cannon_motor.time, "sleep", interrupt_sleep)
    with pytest.raises(InterruptedError):
        motor.run_step()
    reopened = CannonMotor(tmp_path)
    first = reopened.m["last_result"]["task"]
    waits = []

    def recover_sleep(seconds):
        waits.append(seconds)
        if len(waits) == 1:
            assert len(reopened.queue_snapshot()["tasks"]) == 1
            assert reopened.m["executions"][first] == 1
        now[0] += seconds

    monkeypatch.setattr(cannon_motor.time, "sleep", recover_sleep)
    reopened.supervise(max_cycles=3)
    assert waits == [5, 5]
    assert reopened.state == "COMPLETED"
    assert reopened.invariants()["DUPLICATE_EXECUTIONS"] == 0
    assert len(reopened.queue_snapshot()["tasks"]) == 2


def test_real_cli_supervisor_rejects_second_and_stops_after_current(tmp_path):
    import subprocess
    import sys
    import time
    from pathlib import Path

    adapter_script = Path(__file__).resolve().parents[1] / "scripts/mac_adapter.py"
    command = [sys.executable, str(adapter_script), "--state-dir", str(tmp_path),
               "dauerlauf", "--art", "begrenzt", "--limit", "1000000", "--local-fake"]
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                saved = json.loads((tmp_path / "motor.json").read_text())
            except (FileNotFoundError, ValueError):
                saved = {}
            if saved.get("done_count") == 1:
                break
            time.sleep(0.05)  # bounded test observer, no model calls
        else:
            pytest.fail("first local task did not durably finish")
        assert saved["start_limit"] == 1000000
        assert len(json.loads((tmp_path / "queue.json").read_text())["tasks"]) == 1
        duplicate = subprocess.run(command, capture_output=True, text=True, timeout=3, check=True)
        assert json.loads(duplicate.stdout)["reason"] == "supervisor_active"
        MacAdapter(tmp_path).stop()
        output, errors = child.communicate(timeout=10)
        assert child.returncode == 0, errors
        final = json.loads(output)["snapshot"]
        assert final["invariants"]["MAX_ACTIVE"] == 1
        assert final["invariants"]["STARTED"] == 1
        assert final["invariants"]["DONE_COUNT"] == 1
        assert final["invariants"]["DUPLICATE_EXECUTIONS"] == 0
    finally:
        if child.poll() is None:
            child.terminate()  # only the explicitly created isolated test child
            child.communicate(timeout=5)
