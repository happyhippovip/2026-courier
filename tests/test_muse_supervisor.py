"""SIMULATED proof: Muse slots on the canonical Courier path.

Real server/app.py (temp state, test keys) on a local port, real
scripts/mac_worker/daemon.py per slot, and a fake Muse CLI. No real Muse,
no Mac: nothing here is physical proof.
"""
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
SUP_PATH = ROOT / "scripts" / "mac_worker" / "muse_supervisor.py"
WORKER_KEY, VERIFIER_KEY = "sim-worker-key", "sim-verifier-key"
HEALTHY = {"swap_mb": 0.0, "load_1m": 0.5, "mem_free_pct": 80.0}

FAKE_MUSE = r'''
import json, os, sys, time
prompt = sys.stdin.read()
log = os.environ["FAKE_MUSE_LOG"]
with open(log, "a") as f:
    f.write(json.dumps({"cwd": os.getcwd(), "prompt": prompt}) + "\n")
time.sleep(float(os.environ.get("FAKE_MUSE_SLEEP", "0")))
open("out.txt", "w").write("done\n")
print("```json\n" + json.dumps({"status": "SUCCESS", "branch": "muse/sim", "last_commit": "c0ffee1",
                                "next_task": "verify"}) + "\n```")
'''


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Clock:
    def __init__(self): self.t = time.time()
    def __call__(self): return self.t


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", WORKER_KEY)
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", VERIFIER_KEY)
    monkeypatch.setenv("COURIER_STATE_FILE", str(tmp_path / "central.json"))
    server = load_module(f"srv_{tmp_path.name}", ROOT / "server" / "app.py")
    httpd = make_server("127.0.0.1", 0, server.app, threaded=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}"

    muse = tmp_path / "fake_muse.py"
    muse.write_text(FAKE_MUSE)
    (tmp_path / "muse.sh").write_text(f'#!/bin/bash\nexec "{sys.executable}" "{muse}" "$@"\n')
    os.chmod(tmp_path / "muse.sh", 0o755)
    worker_cfg = tmp_path / "worker_config.json"
    worker_cfg.write_text(json.dumps({"WORKER_ID": "unused", "POLL_INTERVAL_SECONDS": 0.1}))
    monkeypatch.setenv("COURIER_SERVER", url)
    monkeypatch.setenv("COURIER_MUSE_CLI", json.dumps({"binary": str(tmp_path / "muse.sh"), "prompt_via": "stdin"}))
    monkeypatch.setenv("FAKE_MUSE_LOG", str(tmp_path / "muse_calls.jsonl"))
    monkeypatch.setenv("COURIER_WALL_DIR", str(tmp_path / "wall"))
    sup = load_module(f"sup_{tmp_path.name}", SUP_PATH)
    (tmp_path / "wall").mkdir()
    sup.write_json(sup.CONFIG_FILE, {"worker_config": str(worker_cfg)})
    http = server.app.test_client()
    auth = {"Authorization": f"Bearer {WORKER_KEY}"}
    yield sup, server, http, auth, tmp_path
    httpd.shutdown()


def add_goal(http, auth, task_id):
    http.post("/goals", headers=auth, json={"goal_text": task_id, "workflow_plan": [
        {"task_id": task_id, "target_agent": "mac", "instruction": f"do {task_id}", "artifacts": ["out.txt"]}]})


def muse_calls(tmp):
    path = tmp / "muse_calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run_until(sup_obj, predicate, clock=None, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if clock: clock.t = time.time() + 10_000
        sup_obj.tick(HEALTHY)
        if predicate():
            return True
        time.sleep(0.1)
    return False


def supervisor(sup, target=4, clock=None):
    sup.cmd_start(target, loop=False)
    gov = sup.CapacityGovernor(target, clock=clock or time.time)
    gov.admitted = target
    return sup.Supervisor(governor=gov, clock=clock or time.time)


def task_state(server, task_id):
    return server.load_state()["tasks"].get(task_id, {})


def test_slot_claims_canonical_task_runs_muse_exits_and_restarts_with_checkpoint(env):
    sup, server, http, auth, tmp = env
    add_goal(http, auth, "t-1")
    clock = Clock()
    s = supervisor(sup, target=1, clock=clock)
    assert run_until(s, lambda: task_state(server, "t-1").get("status") == "RESULT_RECEIVED")
    task = task_state(server, "t-1")
    assert task["worker_id"] == "MUSE-01" and task["result"]["dispatch_id"] == task["dispatch_id"]
    calls = muse_calls(tmp)
    assert len(calls) == 1 and task["dispatch_id"] in calls[0]["prompt"]          # prompt delivered
    assert calls[0]["cwd"].endswith("slots/01/work")
    # normal exit (one task per process) -> same slot restarted
    assert run_until(s, lambda: sup.load_slots()["01"].get("restart_count", 0) >= 1 and
                     sup.load_slots()["01"]["state"] == "RUNNING", clock=clock)
    slot = sup.load_slots()["01"]
    assert slot["last_exit_code"] == 0 and slot["crash_count"] == 0
    view = sup.worker_view("01")
    assert (view["branch"], view["last_commit"], view["next_task"]) == ("muse/sim", "c0ffee1", "verify")
    add_goal(http, auth, "t-2")
    assert run_until(s, lambda: task_state(server, "t-2").get("status") == "RESULT_RECEIVED", clock=clock)
    assert '"branch": "muse/sim"' in muse_calls(tmp)[1]["prompt"]                  # checkpoint resumed
    sup.cmd_stop()
    assert run_until(s, lambda: sup.load_slots()["01"]["state"] == "STOPPED", clock=clock)


def claim_as(http, auth, worker_id):
    http.post("/workers/register", headers=auth, json={"worker_id": worker_id, "capabilities": ["macos"]})
    return http.post("/tasks/claim", headers=auth, json={"worker_id": worker_id}).get_json()["task"]


def seed(sup, slot_id, task):
    state = sup.slot_home(slot_id) / "state"
    state.mkdir(parents=True)
    (state / "current_task.json").write_text(json.dumps(task))


def test_result_ready_is_only_redelivered(env):
    sup, server, http, auth, tmp = env
    add_goal(http, auth, "t-r")
    task = claim_as(http, auth, "MUSE-01")
    payload = {k: task[k] for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")}
    payload.update(run_id="run-before-crash", result_id="result-before-crash", status="SUCCESS",
                   artifacts=[{"path": "out.txt", "sha256": "a" * 64}])
    seed(sup, "01", dict(task, worker_phase="RESULT_READY", result_payload=payload))
    s = supervisor(sup, target=1)
    assert run_until(s, lambda: task_state(server, "t-r").get("status") == "RESULT_RECEIVED")
    stored = task_state(server, "t-r")
    assert stored["result"]["result_id"] == "result-before-crash"
    assert stored["attempt_id"] == task["attempt_id"] and stored["dispatch_id"] == task["dispatch_id"]
    assert muse_calls(tmp) == []                                                   # not recomputed
    sup.cmd_stop()


def test_started_task_is_not_replayed(env):
    sup, server, http, auth, tmp = env
    add_goal(http, auth, "t-s")
    task = claim_as(http, auth, "MUSE-01")
    seed(sup, "01", dict(task, worker_phase="STARTED"))
    s = supervisor(sup, target=1)
    assert run_until(s, lambda: task_state(server, "t-s").get("status") == "HUMAN_REQUIRED")
    assert muse_calls(tmp) == []                                                   # no blind replay
    sup.cmd_stop()


def test_duplicate_slot_and_supervisor_are_prevented(env):
    sup, server, http, auth, tmp = env
    s = supervisor(sup, target=1)
    s.tick(HEALTHY)
    first = sup.load_slots()["01"]["pid"]
    slots = sup.load_slots()
    slots["01"]["state"] = "IDLE"                                                  # lost supervisor state
    sup.save_slots(slots)
    s.tick(HEALTHY)
    assert sup.load_slots()["01"]["pid"] == first and len(s.launcher.children) == 1
    assert sup.acquire_lock() is not None and sup.acquire_lock() is None
    # the daemon itself refuses a second process on the same slot state
    second = s.launcher.start("01", sup.slot_env("01", sup.read_json(sup.CONFIG_FILE, {})))
    deadline = time.time() + 10
    while s.launcher.children["01"].poll() is None and time.time() < deadline:
        time.sleep(0.1)
    assert s.launcher.exit_code("01") == 3 and second
    sup.cmd_stop(terminate=True, launcher=s.launcher)


def test_missing_metrics_block_scale_up(env):
    sup, *_ = env
    clock = Clock()
    sup.cmd_start(4, loop=False)
    s = sup.Supervisor(governor=sup.CapacityGovernor(4, clock=clock, reader=lambda: None), clock=clock)
    s.tick()
    clock.t += 10_000
    s.tick()
    states = [v["state"] for _, v in sorted(sup.load_slots().items())]
    assert states.count("RUNNING") == 1 and states.count("RESOURCE_BLOCKED") == 3  # held at 1
    sup.cmd_stop(terminate=True, launcher=s.launcher)


def test_ramp_and_crash_backoff_to_paused(env):
    sup, *_ = env
    clock = Clock()
    gov = sup.CapacityGovernor(32, clock=clock)
    for expected in (1, 4, 8, 16, 32):
        assert gov.evaluate(HEALTHY) == expected
        clock.t += sup.RAMP_HOLD_SECONDS + 1
    assert gov.evaluate(dict(HEALTHY, mem_free_pct=5.0)) == 16                     # step down, kill nothing

    class Crashy:
        def __init__(self): self.starts = 0
        def start(self, slot_id, env): self.starts += 1; return 99999999
        def is_alive(self, slot_id, pid): return False
        def exit_code(self, slot_id): return 2
    sup.cmd_start(4, loop=False)
    g = sup.CapacityGovernor(4, clock=clock); g.admitted = 4
    s = sup.Supervisor(launcher=Crashy(), governor=g, clock=clock)
    delays = []
    for _ in range(2 * sup.CRASH_LIMIT + 2):
        s.tick(HEALTHY)
        slot = sup.load_slots()["01"]
        if slot["state"] == "BACKOFF":
            delays.append(slot["backoff_until"] - clock.t)
            clock.t = slot["backoff_until"] + 1
    assert sup.load_slots()["01"]["state"] == "PAUSED_ERROR"
    assert delays == sorted(delays) and len(set(delays)) > 1
    assert sup.cmd_resume("01") == 0 and sup.load_slots()["01"]["state"] == "IDLE"


def test_four_slots_are_isolated(env):
    sup, server, http, auth, tmp = env
    for i in range(1, 5):
        add_goal(http, auth, f"t-4-{i}")
    s = supervisor(sup, target=4)
    assert run_until(s, lambda: all(task_state(server, f"t-4-{i}").get("status") == "RESULT_RECEIVED"
                                    for i in range(1, 5)))
    workers = {task_state(server, f"t-4-{i}")["worker_id"] for i in range(1, 5)}
    assert workers == {f"MUSE-0{i}" for i in range(1, 5)}                          # one task per slot
    cwds = {c["cwd"] for c in muse_calls(tmp)}
    assert len(cwds) == 4 and len(muse_calls(tmp)) == 4
    sup.cmd_stop()


def test_stop_prevents_restart(env):
    sup, server, http, auth, tmp = env
    add_goal(http, auth, "t-stop")
    clock = Clock()
    s = supervisor(sup, target=1, clock=clock)
    assert run_until(s, lambda: task_state(server, "t-stop").get("status") == "RESULT_RECEIVED")
    sup.cmd_stop()
    assert run_until(s, lambda: sup.load_slots()["01"]["state"] == "STOPPED", clock=clock)
    starts = len(s.launcher.children)
    clock.t += 10_000
    s.tick(HEALTHY)
    assert sup.load_slots()["01"]["state"] == "STOPPED"


def test_unconfirmed_prompt_method_fails_closed():
    sys.path.insert(0, str(ROOT / "scripts" / "mac_worker"))
    import muse_adapter
    task = {"task_id": "t", "goal_id": "g", "attempt_id": "t:attempt:1", "dispatch_id": "d-1", "instruction": "x"}
    with pytest.raises(muse_adapter.MuseCapabilityUnknown):
        muse_adapter.build_muse_command(task, {}, {})
    with pytest.raises(muse_adapter.MuseCapabilityUnknown):
        muse_adapter.build_muse_command(task, {}, {"prompt_via": "arg"})           # flag not confirmed
    argv, stdin = muse_adapter.build_muse_command(task, {"branch": "b"}, {"prompt_via": "arg", "prompt_flag": "-p"})
    assert argv[:2] == ["muse", "-p"] and "d-1" in argv[2] and stdin is None
