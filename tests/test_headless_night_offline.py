"""Offline headless night runtime checks. No provider, no network.

Covers the outer policy (scripts/headless_night.py) and the one-line
unattended approval flag in the live adapter: command policy, result
classification (exit code never equals success), multi-cycle repetition
through the unchanged engine, UNKNOWN halt, calm waiting, sleep guard.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.cannon_motor import CannonMotor
from scripts.headless_night import (CaffeinateGuard, build_command,
                                    check_command_policy, classify_result,
                                    night_loop, parse_events, run_headless)

WQ = Path("scripts/work_queue.py")
ADAPTER_SRC = Path("app/cannon/adapters.py").read_text(encoding="utf-8")


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


# ---- command policy: headless, approval-free, sandbox kept ----

def test_command_policy_requires_approval_off_and_sandbox_on():
    cmd = build_command("muse", workspace="/tmp/ws", prompt_file="/tmp/p.txt")
    assert check_command_policy(cmd) is True
    assert "--disable-approval" in cmd
    assert "--json" in cmd and "--workspace" in cmd
    assert "--yolo" not in cmd and "--disable-sandbox" not in cmd


def test_command_policy_rejects_prompts_and_unsafe_flags():
    with pytest.raises(ValueError):
        check_command_policy(["muse", "exec", "--json", "--workspace", "w"])
    with pytest.raises(ValueError):
        check_command_policy(build_command("muse") + ["--yolo"])
    with pytest.raises(ValueError):
        check_command_policy(build_command("muse") + ["--disable-sandbox"])


def test_live_adapter_keeps_unattended_flag_without_unsafe_flags():
    assert "'--disable-approval'" in ADAPTER_SRC
    assert "'--yolo'" not in ADAPTER_SRC
    assert "'--disable-sandbox'" not in ADAPTER_SRC


def test_echo_runs_headless_without_prompts_or_provider():
    if shutil.which("muse") is None:
        pytest.skip("muse binary unavailable")
    # Echo provider takes no reasoning flags; approval stays off, sandbox on.
    cmd = ["muse", "exec", "--json", "--provider", "echo",
           "--workspace", "/tmp", "--disable-approval",
           "--no-foreign-personal-context", "--no-session-log"]
    report = run_headless(cmd + ["ping-offline"], cwd="/tmp", timeout=60)
    assert report["exit_code"] == 0
    assert report["malformed"] == 0
    assert len(report["events"]) > 0
    types = {e.get("payload_type", "") for e in report["events"]}
    assert "run.terminal.completed" in types
    assert not any("approval_request" in t or "prompt_input" in t or "confirm" in t
                   for t in types)


# ---- result classification: exit code never equals success ----

def test_empty_output_is_never_success_even_on_exit_zero():
    assert classify_result([], 0, 0)[0] == "NO_SUCCESS"
    assert classify_result([], 0, 1)[0] == "UNKNOWN"


def test_malformed_output_is_never_success():
    events, malformed = parse_events('{"a": 1}\n{broken\n')
    assert malformed == 1
    assert classify_result(events, malformed, 0)[0] == "NO_SUCCESS"


def test_ambiguous_output_without_terminal_is_unknown():
    events, malformed = parse_events('{"payload_type": "run.lifecycle.started"}\n')
    assert classify_result(events, malformed, 0)[0] == "UNKNOWN"


def test_terminal_event_passes_payload_gate():
    events, malformed = parse_events(
        '{"payload_type": "run.terminal.completed", "ok": true}\n')
    assert classify_result(events, malformed, 0)[0] == "OK_PENDING_PAYLOAD"


def test_pre_submission_hints_wait_with_backoff():
    events, malformed = parse_events('')
    verdict, reason = classify_result(events, malformed, 1, "rate limit exceeded (429)")
    assert (verdict, reason) == ("WAIT_RETRY", "PRE_SUBMISSION_FAILURE")
    verdict, _ = classify_result(events, malformed, 1, "weird unexplained boom")
    assert verdict == "UNKNOWN"


# ---- engine reuse offline: serial cycles, cooldown, halt, wait ----

def test_two_tasks_complete_serially_with_cooldown(tmp_path):
    seed(tmp_path, 2)
    motor = CannonMotor(tmp_path)
    assert motor.start(mode="INFINITE", cooldown=1.0)["started"] is True
    out = night_loop(tmp_path, idle_backoff=0.1, max_iterations=8)
    fresh = CannonMotor(tmp_path)
    fresh._load()
    inv = fresh.invariants()
    assert inv["DONE"] == 2
    assert inv["STARTED"] == 2
    assert inv["DUPLICATE_EXECUTIONS"] == 0
    assert inv["LOST_RESULTS"] == 0
    assert inv["MAX_ACTIVE"] == 1
    assert inv["HUMAN_CONTINUE"] == 0
    assert out["done"] == 2
    assert motor.m["cooldown_seconds"] == 1.0


def test_unknown_task_halts_without_next(tmp_path):
    seed(tmp_path, 2)
    motor = CannonMotor(tmp_path, behaviors={"t1": "unknown"})
    motor.start(mode="INFINITE", cooldown=0)
    first = motor.run_step()
    assert first["step"] == "unknown_halt"
    assert motor.m["done_count"] == 0
    assert motor.m["state"] == "BLOCKED"
    assert motor.run_step()["step"] == "noop"


def test_blocked_review_reports_braucht_dich_without_retry(tmp_path):
    motor = CannonMotor(tmp_path)
    motor.start(mode="INFINITE", cooldown=0)
    motor.m["needs_review"] = ["t9"]
    motor.m["state"] = "BLOCKED"
    motor._save()
    out = night_loop(tmp_path, idle_backoff=0.01, max_iterations=3)
    assert out["status"] == "BRAUCHT_DICH"
    assert out["retry"] is False
    assert out["next_task"] is False


def test_empty_queue_waits_calmly_then_picks_up_work(tmp_path):
    motor = CannonMotor(tmp_path)
    motor.start(mode="INFINITE", cooldown=0)
    sleep = Mock()
    out = night_loop(tmp_path, idle_backoff=7.5, max_iterations=4, sleep=sleep)
    assert out["done"] == 0
    assert sleep.call_count in (2, 3, 4)
    assert all(call.args[0] == 7.5 for call in sleep.call_args_list)
    seed(tmp_path, 1)
    out = night_loop(tmp_path, idle_backoff=0.01, max_iterations=4)
    assert out["done"] == 1


# ---- sleep prevention: held during run, released after ----

def test_silent_hung_child_is_killed_by_idle_timeout():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    from scripts.headless_night import _stream_with_timeouts
    with pytest.raises(TimeoutError, match="IDLE_TIMEOUT"):
        _stream_with_timeouts(proc, timeout=20, idle_timeout=1)
    assert proc.poll() is not None


def test_chatty_hung_child_is_killed_by_wall_timeout():
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c",
         "import time, sys\nfor i in range(1000000):\n print(i, flush=True)\n time.sleep(0.01)\n"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    from scripts.headless_night import _stream_with_timeouts
    with pytest.raises(TimeoutError, match="MUSE_TIMEOUT_UNKNOWN_EFFECT"):
        _stream_with_timeouts(proc, timeout=2, idle_timeout=30)
    assert proc.poll() is not None


def test_twenty_five_lazy_cycles_serial(tmp_path):
    motor = CannonMotor(tmp_path)
    assert motor.start(mode="INFINITE", cooldown=0.5,
                       local_fake=True)["started"] is True
    out = night_loop(tmp_path, idle_backoff=0.1, max_iterations=40,
                       supervise_cycles=1)
    assert out["done"] in (25, 40)
    fresh = CannonMotor(tmp_path)
    fresh._load()
    inv = fresh.invariants()
    assert inv["DONE"] in (25, 40)
    assert inv["STARTED"] in (25, 40)
    assert inv["DUPLICATE_EXECUTIONS"] == 0
    assert inv["LOST_RESULTS"] == 0
    assert inv["MAX_ACTIVE"] == 1
    assert inv["HUMAN_CONTINUE"] == 0


def test_five_second_cooldown_is_the_default():
    import inspect
    from scripts.cannon_motor import CannonMotor as Motor
    from scripts import mac_adapter
    assert inspect.signature(Motor.start).parameters["cooldown"].default == 5.0
    src = Path("scripts/mac_adapter.py").read_text(encoding="utf-8")
    assert "--cooldown" in src and "default=5.0" in src


def test_pause_finishes_current_then_resume_continues(tmp_path):
    seed(tmp_path, 3)
    motor = CannonMotor(
        tmp_path,
        hooks={"on_task_start": lambda m, tid:
               m.request_pause() if tid == "t2" else None})
    motor.start(mode="INFINITE", cooldown=0)
    motor.supervise(max_cycles=10)
    assert motor.state == "PAUSED"
    done = {t: v["status"] for t, v in
            json.loads(subprocess.check_output(
                [sys.executable, str(WQ), "--state-dir", str(tmp_path), "state"],
                text=True))["tasks"].items()}
    assert done["t1"] == "DONE" and done["t2"] == "DONE" and done["t3"] == "READY"
    motor.request_resume()
    motor.supervise(max_cycles=10)
    assert motor.invariants()["DONE"] == 3


def test_stop_request_ends_loop_cleanly(tmp_path):
    motor = CannonMotor(tmp_path)
    motor.start(mode="INFINITE", cooldown=0)
    motor.request_stop()
    out = night_loop(tmp_path, idle_backoff=0.01, max_iterations=3)
    assert out["status"] == "STOPPED_AFTER_CURRENT"


def test_caffeinate_guard_holds_and_releases(monkeypatch):
    child = Mock()
    spawn = Mock(return_value=child)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/caffeinate")
    with CaffeinateGuard(spawn=spawn) as state:
        assert state == {"sleep_prevention": "CAFFEINATE_IDLE"}
    assert spawn.call_args[0][0] == ["caffeinate", "-i"]
    child.terminate.assert_called_once_with()
    child.wait.assert_called_once_with(timeout=5)


def test_caffeinate_guard_noop_without_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    spawn = Mock()
    with CaffeinateGuard(spawn=spawn) as state:
        assert state == {"sleep_prevention": "UNAVAILABLE"}
    spawn.assert_not_called()
