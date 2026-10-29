import pytest; pytest.importorskip("fcntl")
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
prompt = sys.argv[-1]
workspace = sys.argv[sys.argv.index("--workspace") + 1]
log = os.environ["FAKE_MUSE_LOG"]
with open(log, "a") as f:
    f.write(json.dumps({"cwd": os.getcwd(), "prompt": prompt}) + "\n")
time.sleep(float(os.environ.get("FAKE_MUSE_SLEEP", "0")))
open(os.path.join(workspace, "out.txt"), "w").write("done\n")
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
    monkeypatch.setenv("COURIER_MUSE_CLI", json.dumps({"binary": str(tmp_path / "muse.sh"), "protocol": "headless-v1"}))
    monkeypatch.setenv("FAKE_MUSE_LOG", str(tmp_path / "muse_calls.jsonl"))
    monkeypatch.setenv("COURIER_WALL_DIR", str(tmp_path / "wall"))
    sup = load_module(f"sup_{tmp_path.name}", SUP_PATH)
    (tmp_path / "wall").mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sup.write_json(sup.CONFIG_FILE, {"worker_config": str(worker_cfg), "workspace": str(workspace)})
    # Test-only bootstrap: no Keychain or real resource probes in worker processes.
    bootstrap = tmp_path / "fake_config_daemon.py"
    bootstrap.write_text(
        f"import sys, os, signal\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
        f"sys.path.insert(0, {str(ROOT / 'scripts' / 'mac_worker')!r})\n"
        "import daemon as d\n"
        "d.load_config = lambda: {'COURIER_SERVER': os.environ['COURIER_SERVER'], "
        "'COURIER_API_KEY': os.environ['COURIER_API_KEY'], 'WORKER_ID': os.environ['COURIER_WORKER_ID'], "
        "'POLL_INTERVAL_SECONDS': 0.1}\n"
        "d.resource_ready = lambda: True\n"
        "d.cost_gate = lambda resource_id, estimated_cost_eur=None: {'allowed': True}\n"
        "def stop(*args): raise d.WorkerShutdown()\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        "try: d.loop()\nexcept d.WorkerShutdown: pass\n")
    monkeypatch.setattr(sup, "DAEMON", bootstrap)
    launchers = []
    real_launcher_cls = sup.ProcessLauncher
    class TrackingLauncher(real_launcher_cls):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            launchers.append(self)
    monkeypatch.setattr(sup, "ProcessLauncher", TrackingLauncher)
    http = server.app.test_client()
    auth = {"Authorization": f"Bearer {WORKER_KEY}"}
    try:
        yield sup, server, http, auth, tmp_path
    finally:
        for l in launchers:
            sup.cmd_stop(terminate=True, launcher=l)
        sup.cmd_stop(terminate=True)
        httpd.shutdown()


def add_goal(http, auth, task_id):
    http.post("/goals", headers=auth, json={"goal_text": task_id, "workflow_plan": [
        {"task_id": task_id, "target_agent": "mac", "instruction": f"do {task_id}", "artifacts": ["out.txt"]}]})


def muse_calls(tmp):
    path = tmp / "muse_calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run_until(sup_obj, predicate, clock=None, timeout=60.0):
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
    # The in-process server writes the state file and its .sig in two steps
    # under STATE_LOCK; reading without it can see a new state with the old
    # signature and raise "signature mismatch" (flaky, ~1 in 12 runs).
    with server.STATE_LOCK:
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
    assert '"branch": "muse/sim"' not in muse_calls(tmp)[1]["prompt"]  # new task, not foreign context
    assert list((sup.slot_home("01") / "state").glob("checkpoint.quarantine-*.json"))
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
    from scripts.integration_contract import canonical_result_id
    sup, server, http, auth, tmp = env
    add_goal(http, auth, "t-r")
    task = claim_as(http, auth, "MUSE-01")
    payload = {k: task[k] for k in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")}
    payload.update(run_id="run-before-crash", status="SUCCESS",
                   artifacts=[{"path": "out.txt", "sha256": "a" * 64}])
    payload["result_id"] = canonical_result_id(payload)
    seed(sup, "01", dict(task, worker_phase="RESULT_READY", result_payload=payload))
    s = supervisor(sup, target=1)
    assert run_until(s, lambda: task_state(server, "t-r").get("status") == "RESULT_RECEIVED")
    stored = task_state(server, "t-r")
    assert stored["result"]["result_id"] == payload["result_id"]
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
    lock = sup.acquire_lock()
    assert lock is not None and sup.acquire_lock() is None
    lock.close()
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
    assert states.count("RUNNING") == 0 and states.count("RESOURCE_BLOCKED") == 4
    sup.cmd_stop(terminate=True, launcher=s.launcher)


def test_ramp_and_crash_backoff_to_paused(env):
    sup, *_ = env
    clock = Clock()
    gov = sup.CapacityGovernor(32, clock=clock)
    for expected in (1, 4, 8, 16, 32):
        assert gov.evaluate(HEALTHY) == expected
        clock.t += sup.RAMP_HOLD_SECONDS + 1
    assert gov.evaluate(dict(HEALTHY, mem_free_pct=5.0)) == 0
    assert gov.admitted == 16

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
    argv, stdin = muse_adapter.build_muse_command(task, {}, {"protocol": "headless-v1"},
        slot_id="01", workspace="/Users/user/Downloads/2026-courier")
    assert argv[:2] == ["muse", "exec"] and "d-1" in argv[-1] and stdin is None


def test_slot_model_12_fields(env):
    sup, server, http, auth, tmp = env
    sup.save_slots({
        "01": {"slot_id": "01", "state": "RUNNING", "pid": 99999, "owner": "happyhippovip", "agent": "MUSE"}
    })
    model = sup.slot_model("01")
    assert len(model) == 12
    required_keys = {
        "SLOT_ID", "HOST", "AGENT", "PROCESS_STATUS", "CURRENT_WORKKEY", "OWNER",
        "LEASE", "LAST_ACTIVITY", "BACKOFF", "RESOURCE_STATUS", "SOURCE_PROVENANCE", "VERIFICATION_STATUS"
    }
    assert set(model.keys()) == required_keys
    assert model["SLOT_ID"] == "01"
    assert model["PROCESS_STATUS"] == "ALIVE"
    assert model["OWNER"] == "happyhippovip"


def test_deterministic_bulletin_feed(env, monkeypatch):
    sup, server, http, auth, tmp = env
    sup.save_slots({
        "01": {"slot_id": "01", "state": "RUNNING", "pid": 99999, "owner": "happyhippovip"},
        "02": {"slot_id": "02", "state": "BACKOFF", "backoff_until": time.time() + 10}
    })
    events = sup.bulletin_feed()
    assert isinstance(events, list)
    codes = [e["code"] for e in events]
    assert "SLOT_RUNNING" in codes
    assert "SLOT_BACKOFF" in codes


def test_cmd_build_initialises_slots_without_spawning(env):
    sup, server, http, auth, tmp = env
    assert sup.cmd_build(4) == 0
    assert sup.CONFIG_FILE.exists()
    config = sup.read_json(sup.CONFIG_FILE, {})
    assert config["target"] == 4
    slots = sup.load_slots()
    assert len(slots) == 4
    for i in range(1, 5):
        sid = f"{i:02d}"
        home = sup.slot_home(sid)
        assert (home / "work").is_dir()
        assert (home / "logs").is_dir()
        assert (home / "state").is_dir()
        assert (home / "state.json").exists()
        assert slots[sid]["state"] == "IDLE"
        assert not slots[sid].get("pid")


def test_cmd_reconcile_cleans_orphaned_and_unowned_processes(env):
    sup, server, http, auth, tmp = env
    sup.save_slots({
        "01": {"slot_id": "01", "state": "RUNNING", "pid": 999999, "process_identity": "999999:dead"},
        "02": {"slot_id": "02", "state": "STARTING", "pid": None},
    })
    class MockLauncher:
        def is_alive(self, sid, pid): return False
        def owned(self, sid, pid, identity): return False
        def terminate(self, sid, pid, identity): return True
        def exit_code(self, sid): return 1
    assert sup.cmd_reconcile(launcher=MockLauncher()) == 0
    slots = sup.load_slots()
    assert slots["01"]["pid"] is None
    assert slots["01"]["state"] == "PAUSED_ERROR"
    assert "ORPHANED_CLEANUP" in slots["01"].get("blocker", "")


def test_cmd_notaus_terminates_all_processes(env):
    sup, server, http, auth, tmp = env
    sup.save_slots({
        "01": {"slot_id": "01", "state": "RUNNING", "pid": 12345},
    })
    class MockLauncher:
        def terminate(self, sid, pid, identity): return True
    assert sup.cmd_notaus(launcher=MockLauncher()) == 0
    assert sup.STOP_FILE.exists()
    slots = sup.load_slots()
    assert slots["01"]["state"] == "STOPPED"
    assert slots["01"]["pid"] is None


def test_kolibri_integration_with_muse_wall(env, monkeypatch):
    sup, server, http, auth, tmp = env
    import courier_hub.kolibri_data as kd
    monkeypatch.setenv("COURIER_WALL_DIR", str(sup.WALL_DIR))

    # Build wall with 1 slot
    assert sup.cmd_build(1) == 0

    # Resolve wall path
    wall_dir, label = kd.resolve_muse_wall(ROOT)
    assert wall_dir == sup.WALL_DIR / "slots"

    # Save active slot with current alive process PID
    current_pid = os.getpid()
    sup.save_slots({
        "01": {"slot_id": "01", "state": "RUNNING", "pid": current_pid, "last_started_at": time.time()}
    })
    assert (sup.slot_home("01") / "state.json").exists()

    observed = kd.utc_now()
    snapshot = kd.read_muse_wall(ROOT, wall_dir, label, observed, {"available": True, "rows": []})
    assert snapshot["available"] is True
    assert snapshot["active"] is True
    assert snapshot["value"] == "1"
    station = [s for s in snapshot["stations"] if s["id"] == "MUSE-01"][0]
    assert station["heartbeat"] is True
    assert station["state"]["value"] == "RUNNING"
    assert station["process"]["value"] == "present"


def test_main_cli_dispatch(env, monkeypatch):
    sup, server, http, auth, tmp = env
    assert sup.main(["wall-aufbauen", "4"]) == 0
    assert sup.main(["wall-ordnen"]) == 0
    assert sup.main(["wall-status"]) == 0
    assert sup.main(["wall-bulletin"]) == 0
    assert sup.main(["wall-notaus"]) == 0
    assert sup.STOP_FILE.exists()


def test_owned_popen_stops_when_ps_identity_is_missing(env, monkeypatch):
    sup, server, http, auth, tmp = env
    monkeypatch.setattr(sup, "process_identity", lambda pid: None)
    launcher = sup.ProcessLauncher()
    s = sup.Supervisor(launcher=launcher)
    sup.cmd_start(1, loop=False)
    s.tick(HEALTHY)
    slots = sup.load_slots()
    assert slots["01"]["state"] == "RUNNING"
    pid = slots["01"]["pid"]
    assert pid is not None
    assert launcher.identities.get("01") is None
    # Must terminate cleanly and reap child despite missing ps identity
    assert sup.cmd_stop(terminate=True, launcher=launcher) == 0
    proc = launcher.children.get("01")
    assert proc.poll() is not None


def test_teardown_leaves_no_slot_processes(env):
    sup, server, http, auth, tmp = env
    add_goal(http, auth, "t-leak-check")
    clock = Clock()
    s = supervisor(sup, target=1, clock=clock)
    assert run_until(s, lambda: task_state(server, "t-leak-check").get("status") == "RESULT_RECEIVED")
    sup.cmd_stop(terminate=True, launcher=s.launcher)
    for sid, proc in s.launcher.children.items():
        assert proc.poll() is not None


def test_supervisor_acquire_lock_integrates_authority_store(env):
    """Proves that mac supervisor acquire_lock binds to authority.db LeaseStore."""
    from courier_runtime.lease import LeaseStore

    sup, server, http, auth, tmp = env
    auth_db = sup.WALL_DIR / "authority.db"

    lock = sup.acquire_lock()
    assert lock is not None

    # Verify store has active lease
    store = LeaseStore(str(auth_db))
    current = store.current("supervisor:mac_wall")
    assert current is not None
    assert "mac_supervisor" in current.holder
    store.close()

    # Second acquisition fails
    second_lock = sup.acquire_lock()
    assert second_lock is None

    # Release frees lease
    lock.close()
    store = LeaseStore(str(auth_db))
    assert store.current("supervisor:mac_wall") is None
    store.close()


def _fresh_supervisor(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_WALL_DIR", str(tmp_path / "wall"))
    return load_module(f"sup_lease_{tmp_path.name}", SUP_PATH)


def test_missing_authority_store_does_not_keep_the_supervisor_lock(tmp_path, monkeypatch):
    sup = _fresh_supervisor(tmp_path, monkeypatch)
    original = sup.get_authority_store
    monkeypatch.setattr(sup, "get_authority_store", lambda: None)
    with pytest.raises(RuntimeError, match="refusing to run without a writer lease"):
        sup.acquire_lock()

    monkeypatch.setattr(sup, "get_authority_store", original)
    lock = sup.acquire_lock()
    assert lock is not None
    assert lock.lease is not None
    lock.close()


def test_authority_lease_error_is_not_another_supervisor(tmp_path, monkeypatch):
    sup = _fresh_supervisor(tmp_path, monkeypatch)

    class BrokenStore:
        def acquire(self, *_args, **_kwargs):
            raise RuntimeError("authority.db unreadable")

    monkeypatch.setattr(sup, "get_authority_store", lambda: BrokenStore())
    with pytest.raises(RuntimeError, match="authority.db unreadable"):
        sup.acquire_lock()

    monkeypatch.undo()
    monkeypatch.setenv("COURIER_WALL_DIR", str(tmp_path / "wall"))
    lock = sup.acquire_lock()
    assert lock is not None
    lock.close()


def test_authority_lease_conflict_defers_supervisor(tmp_path, monkeypatch):
    from courier_runtime.lease import LeaseConflict

    sup = _fresh_supervisor(tmp_path, monkeypatch)

    class HeldStore:
        def acquire(self, *_args, **_kwargs):
            raise LeaseConflict("supervisor scope is held")

    monkeypatch.setattr(sup, "get_authority_store", lambda: HeldStore())
    assert sup.acquire_lock() is None

    monkeypatch.undo()
    monkeypatch.setenv("COURIER_WALL_DIR", str(tmp_path / "wall"))
    lock = sup.acquire_lock()
    assert lock is not None
    lock.close()



